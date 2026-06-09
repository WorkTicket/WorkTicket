# Runbook: Redis Broker Eviction / Memory Pressure

## Symptoms
- `RedisBrokerEvictingKeys` alert firing
- `workticket_redis_evicted_keys_total` > 0
- Jobs stuck in "queued" state, never picked up by workers
- Customers reporting silent job loss

## Impact
Tasks silently disappear from the queue. Celery workers never receive them.
AI jobs are permanently lost unless detected and re-dispatched.

## Immediate Mitigation

### 1. Check Redis eviction stats
```bash
redis-cli -a "$REDIS_PASSWORD" INFO stats | grep evicted_keys
```

### 2. Check current maxmemory policy
```bash
redis-cli -a "$REDIS_PASSWORD" CONFIG GET maxmemory-policy
# Expected: noeviction
```

### 3. Fix the eviction policy (hot fix)
```bash
redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory-policy noeviction
redis-cli -a "$REDIS_PASSWORD" CONFIG SET maxmemory 200mb
```

### 4. Verify the fix persists in config
Update `docker-compose.yml` for redis-broker:
```yaml
command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}", "--maxmemory-policy", "noeviction", "--maxmemory", "200mb", "--appendonly", "yes"]
```

### 5. Find and re-dispatch lost jobs
Run SQL to find jobs stuck in "queued" with no heartbeat:
```sql
SELECT id, company_id, created_at FROM jobs
WHERE ai_processing_state = 'queued'
  AND ai_processing_updated_at < NOW() - INTERVAL '10 minutes';
```

For each job, re-dispatch via the API or Celery beat:
- `scan_for_stalled_ai_jobs` beat task runs every 5 minutes
- Only recovers jobs WITH media (images/audio)
- Text-only jobs need manual re-dispatch

### 6. Clear backlog
Check queue depth and purge if needed:
```bash
redis-cli -a "$REDIS_PASSWORD" LLEN default
redis-cli -a "$REDIS_PASSWORD" DEL default  # Only if all tasks are known duplicates
```

## Root Cause Fix
Ensure `docker-compose.yml` for `redis-broker` uses:
```
--maxmemory-policy noeviction --maxmemory 200mb
```
NOT `allkeys-lru`.

## Prevention
- Monitor `workticket_redis_evicted_keys_total` (alert at > 0)
- Monitor `workticket_redis_memory_used_bytes / workticket_redis_memory_max_bytes` (alert at > 80%)
- Weekly capacity review of Redis broker memory
