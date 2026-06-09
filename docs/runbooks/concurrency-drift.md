# Concurrency Counter Negative Drift (C-4)

## Symptoms
- `rate(workticket_concurrency_counter_negative_total[5m]) > 0` alert firing
- Concurrency counter in Redis goes negative for a company_id
- New AI jobs may be blocked from running due to negative counter

## Root Cause
The Lua DECR script in `_RELEASE_LUA` is not properly capping at 0, or a concurrency
release is called more times than acquire. This can happen when:
1. A task's `finally` block releases concurrency after it was already released
2. The Lua script has a race condition in the DECR-then-check path

## Verification
1. Check which company_ids have negative counters:
   ```
   redis-cli --scan --pattern "conc:*" | while read key; do echo "$key: $(redis-cli GET $key)"; done
   ```
2. Check the Lua script in `app/billing/concurrency.py`:
   - `_RELEASE_LUA` should check `count <= 0` before DECR and `new_count <= 0` after DECR
   - Both paths should `DEL` the key and return 0

## Recovery
1. Reset negative counters manually:
   ```
   redis-cli DEL conc:<company_id>
   ```
2. Verify the fix: run the chaos test `test_c4_concurrency_limit.py` with 1000 iterations

## Prevention
- The Lua script in `_RELEASE_LUA` must never allow the counter to go below 0
- The `company_concurrency.release()` in `process_job_task` must be idempotent
- Monitor the ConcurrencyCounterDrift alert
