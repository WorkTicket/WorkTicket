# Worker Stuck Runbook

## Symptoms
- `rate(workticket_jobs_completed_total[5m]) == 0` alert firing (`CeleryWorkerStalled`)
- Active workers count drops to 0 for a queue
- Tasks in `queued` state for > 60 min
- **Fix 1.1/1.2**: Event loop corruption and transaction-held-across-AI-call have been fixed.
  Workers should no longer hang due to event loop state or DB connection exhaustion.

## Detection
```bash
# Check worker status
celery -A celery_app status

# Check active queues
celery -A celery_app inspect active

# Check reserved tasks
celery -A celery_app inspect reserved

# View worker logs
docker logs --tail=100 workticket-celery-worker-1
```

## Steps

1. **Confirm worker is stuck**
   ```bash
   celery -A celery_app inspect ping --timeout=10
   ```
   Expected: `pong` from each worker. If no response, worker is deadlocked.

2. **Check for event loop corruption** (fix 1.2 addressed this)
   ```bash
   docker logs workticket-celery-worker-1 2>&1 | grep -i "event loop\|shutdown_asyncgens\|RuntimeError"
   ```
   If `"Event loop error"` messages appear, the fix added `loop.shutdown_asyncgens()` —
   a worker restart will clear the state.

3. **Check for DB connection exhaustion** (fix 1.1 addressed this)
   ```bash
   docker logs workticket-celery-worker-1 2>&1 | grep -i "timeout.*connection\|pool.*exhausted"
   ```
   The DB transaction is no longer held across the AI gateway call, so connection
   pool starvation should no longer cause worker stalling.

4. **Force-restart stuck worker**
   ```bash
   docker compose restart celery-worker
   ```
   Wait 30s. Re-check with `celery inspect ping`.

5. **Drain queue if backlogged**
   ```bash
   # Check queue depth
   redis-cli -n 0 LLEN default
   
   # If depth > 1000, drain to DLQ selectively
   celery -A celery_app control rate_limit default 10/m
   ```

6. **Replay from DLQ**
   ```bash
   curl -X POST http://localhost:8000/api/v1/billing/dlq/replay \
     -H "Content-Type: application/json" \
     -d '{"batch_size": 100}'
   ```

7. **Root cause analysis**
   - Check Celery worker logs for `deadlock` or `timeout`
   - Check Redis `SLOWLOG GET 10` for slow operations
   - Check DB `pg_stat_activity` for idle-in-transaction queries
   - Check `workticket_concurrency_acquire_failures_total` — Redis may be blocking AI processing

## Prevention
- `CELERY_WORKER_CONCURRENCY=1` — each worker processes one task at a time
- `visibility_timeout=480` — matches `task_time_limit + 180s` buffer
- Monitor `workticket_worker_forced_kill_total` — spikes indicate grace period issues
- Monitor `workticket_broker_redis_memory_pct` — broker OOM can cause silent task loss

## Related
- `ops/runbooks/redis-oom.md` — if broker Redis is the root cause
- `ops/runbooks/dlq-recovery.md` — for replaying lost tasks
- `ops/runbooks/concurrency-drift.md` — if concurrency limiter is blocking
