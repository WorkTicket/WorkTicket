# Redis OOM (Out-of-Memory) Runbook

## Symptoms

- `OOM command not allowed when used memory > 'maxmemory'` errors in worker logs
- Celery task dispatch failures
- Metric: `workticket_redis_memory_used_bytes / workticket_redis_memory_max_bytes > 0.8` alert firing
- Redis eviction counter increasing (if not using `noeviction` policy)

## Impact

- **Task queue**: New tasks cannot be enqueued (broker full)
- **PubSub**: WebSocket status updates fail, fall back to DB polling
- **Rate limiting**: Falls back to local in-memory tracking (per-replica limits applied)
- **Concurrency**: Falls back to local state tracking
- **DLQ**: Emergency JSONL fallback activated for dead letter entries

## Immediate Mitigation

### 1. Identify the memory consumer

```bash
redis-cli -h <redis-host> -p 6379 MEMORY STATS
redis-cli -h <redis-host> -p 6379 MEMORY DOCTOR
redis-cli -h <redis-host> -p 6379 --bigkeys
```

### 2. Check for task backlog

```bash
redis-cli -h <redis-host> -p 6379 LLEN celery
redis-cli -h <redis-host> -p 6379 LLEN beat
```

If the default queue has >10K items, the workers may be stalled.

### 3. Check for unbounded result keys

```bash
redis-cli -h <redis-host> -p 6379 --scan --pattern "celery-task-meta-*" | wc -l
```

If >100K keys, `result_expires` may not be configured (should be 3600s).

### 4. Flush stale results (last resort)

```bash
# Only if result_expires is newly configured and backlog exists:
redis-cli -h <redis-host> -p 6379 --scan --pattern "celery-task-meta-*" | head -50000 | xargs redis-cli DEL
```

### 5. Temporarily increase maxmemory

```bash
redis-cli -h <redis-host> -p 6379 CONFIG SET maxmemory 2gb
```

Then investigate root cause and restore normal limit.

## Root Cause Investigation

| Cause | Check | Fix |
|-------|-------|-----|
| Unbounded result keys | `result_expires` configuration | Set `result_expires = 3600` in Celery config |
| Task backlog | Queue depth metrics | Scale workers, check for stuck tasks |
| Celery broker accumulation | `celery purge -A workticket` after verifying | Purge only after confirming no in-flight tasks |
| Large payloads | Task payload size > 1MB | Audit `enqueue_job_task` callers for oversized payloads |
| Redis pub/sub channels | `PUBSUB CHANNELS` count | Check `job_status:*` channel count, ensure cleanup |

## Prevention

1. `result_expires = 3600` is configured in `celery_app.py`
2. `maxmemory-policy noeviction` on broker Redis (prevents data loss)
3. Monitor `workticket_redis_memory_used_bytes / max_bytes < 0.8`
4. Alert on `workticket_redis_evicted_keys_total > 0` (indicates wrong eviction policy)
5. Regular DLQ replay via `replay_dlq_fallback` beat task

## Recovery

After resolving the OOM condition:

1. Verify broker health: `redis-cli PING`
2. Verify worker connectivity: check worker logs for reconnection messages
3. Verify DLQ integrity: check `replay_dlq_fallback` task ran successfully
4. Verify task processing: submit a test job through the API
5. Verify WebSocket: confirm PubSub fallback is no longer active (`ws_db_poll_count_total` returns to normal)
