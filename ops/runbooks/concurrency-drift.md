# Concurrency Drift Runbook

## Overview
The concurrency limiter (`CompanyConcurrencyLock`) controls how many AI jobs
can run simultaneously per company. It uses Redis Lua scripts for atomic
acquire/release with TTL-based auto-cleanup.

**Fix 1.3**: The local in-memory fallback (`_local_acquire`) has been **removed**.
When Redis is unavailable, `acquire()` returns `False` (fail-closed) instead of
falling back to approximate local counting that could drift across replicas.

## Detection
- **Alert**: `ConcurrencyCounterNegative` — a counter went negative (rare, indicates bug)
- **Alert**: `ConcurrencyAcquireFailures` — Redis unavailable, AI jobs being blocked
- **Symptom**: AI jobs stuck in `queued` state for a specific company
- **Symptom**: `workticket_concurrency_acquire_failures_total` incrementing

## Triage
1. Check which companies are affected:
   ```bash
   redis-cli -a $REDIS_PASSWORD KEYS 'conc:*'
   ```
   Each key is `conc:{company_id}` with the current count as value.

2. Check TTL on stuck keys:
   ```bash
   redis-cli -a $REDIS_PASSWORD TTL conc:{company_id}
   ```
   Keys auto-expire after 300s (5 minutes). If TTL is high and the count is stuck,
   the key may be orphaned.

3. Check concurrency metrics:
   - `workticket_concurrency_counter_negative_total` — release/acquire imbalance
   - `workticket_concurrency_acquire_failures_total` — Redis unavailable

## Manual Recovery
If a concurrency key is stuck with a positive count and no jobs running:

1. **Delete the stale key**:
   ```bash
   redis-cli -a $REDIS_PASSWORD DEL conc:{company_id}
   ```
   Verify: `redis-cli -a $REDIS_PASSWORD EXISTS conc:{company_id}` → 0

2. **If multiple keys are stuck**, run cleanup:
   ```bash
   redis-cli -a $REDIS_PASSWORD EVAL "
     local keys = redis.call('KEYS', 'conc:*')
     for _, k in ipairs(keys) do
       local ttl = redis.call('TTL', k)
       if ttl > 0 then
         redis.call('DEL', k)
       end
     end
     return #keys
   " 0
   ```

3. **Automated cleanup**: The `cleanup_stale()` method runs as part of the
   concurrency limiter and deletes keys with TTL <= 0. This runs on each
   `acquire()` call and periodically via beat task.

## Prevention
- Redis TTL of 300s ensures keys auto-expire if a worker crashes
- The `release()` method uses a Lua script that decrements atomically
- Negative counter detection fires `ConcurrencyCounterNegative` alert
- After fix 1.3, the system fail-closes when Redis is unavailable — no drift possible

## Related
- `ops/runbooks/redis-oom.md` — if Redis outage causes acquire failures
- `ops/runbooks/worker-stuck.md` — if workers can't acquire concurrency
