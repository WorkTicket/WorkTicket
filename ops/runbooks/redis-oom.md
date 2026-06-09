# Redis OOM Runbook

## Detection
- **Alert**: `BrokerRedisMemoryHigh` (>80% maxmemory, 3m sustained)
- **Alert**: `BrokerRedisWriteFailures` (writes failing — OOM imminent)
- **Alert**: `RedisEvictionsDetected` (keys being evicted on cache Redis)
- **Symptom**: Tasks fail to enqueue, Celery workers report broker errors

The broker health check now includes a **write probe** (`SET health:probe EX 2`) and
a **memory check** (`INFO memory` — warns at >80% via `workticket_broker_redis_memory_pct`).

## Triage
1. Check broker health metrics:
   - `workticket_broker_redis_memory_pct` — current memory %
   - `increase(workticket_redis_write_failures_total[5m])` — write failure rate
2. Direct Redis inspection:
   ```bash
   redis-cli -a $REDIS_PASSWORD INFO memory | grep -E "used_memory|maxmemory|maxmemory_policy"
   redis-cli -a $REDIS_PASSWORD MEMORY STATS
   redis-cli -a $REDIS_PASSWORD DBSIZE
   ```
3. Check `/readyz` endpoint for `redis` component status
4. Check Celery queue depths (via `/readyz` or `redis-cli LLEN default`)

## Mitigation (Immediate)
1. **Temporarily increase maxmemory** (buys time):
   ```bash
   redis-cli -a $REDIS_PASSWORD CONFIG SET maxmemory 2gb
   ```
   Then update `docker-compose.yml` permanently.

2. **Clear non-critical keys** if queue is empty:
   ```bash
   redis-cli -a $REDIS_PASSWORD EVAL "return redis.call('DEL', unpack(redis.call('KEYS', 'health:*')))" 0
   ```

3. **If all else fails, restart Redis**:
   ```bash
   docker compose restart redis-broker
   ```
   ⚠️ This clears the queue — tasks will be lost unless `acks_late=True` and workers are still alive.

## Post-Recovery
1. **Verify queue recovery**: check `workticket_celery_queue_depth_*` metrics
2. **Monitor memory growth**: watch `workticket_broker_redis_memory_pct` over next hour
3. **Replay lost tasks**: if tasks were lost, use DLQ recovery runbook
4. **Root cause**: identify what filled the broker — task payload bloat, queue backup, or leak

## Prevention
- The write probe now detects OOM conditions one write-cycle before complete failure
- Memory monitoring at >80% gives ~2-3 minutes of warning before OOM at 1GB
- Consider increasing `--maxmemory` to 2GB in production
- Monitor per-queue depth to catch build-up early: `CeleryQueueDefaultGrowing` alerts
- Task payload size should be kept under 10KB — large payloads fill memory faster

## Related
- `ops/runbooks/queue-backup.md` — for queue depth investigation
- `ops/runbooks/dlq-recovery.md` — for replaying lost tasks
- `ops/runbooks/worker-stuck.md` — if workers stop processing
