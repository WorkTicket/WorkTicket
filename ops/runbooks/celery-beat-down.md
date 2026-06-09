# Celery Beat Down Runbook

## Symptoms
- Scheduled tasks not executing (DLQ purge, quota reset, stale job cleanup)
- Alert: `beat:lock:*` Redis key stale for > 300s
- No beat task logs in the last 5 minutes

## Detection
```bash
# Check beat lock keys
redis-cli KEYS "beat:lock:*"

# Check beat container
docker ps --filter "name=celery-beat"

# Check beat logs
docker logs --tail=50 workticket-celery-beat-1
```

## Steps

1. **Restart primary beat**
   ```bash
   docker compose restart celery-beat
   ```
   Wait 30s for schedule to initialize.

2. **Verify beat is running tasks**
   ```bash
   # Check every 30s — key should refresh
   redis-cli TTL "beat:lock:cleanup-stale-jobs"
   ```

3. **If primary fails — standby takes over**
   The `celery-beat-standby` container has the same schedule.
   `_acquire_beat_lock` ensures exactly one execution per TTL window.
   Verify:
   ```bash
   docker logs --tail=20 workticket-celery-beat-standby-1 | grep "beat lock"
   ```

4. **Manually trigger critical beat tasks**
   ```bash
   curl -X POST http://localhost:8000/api/v1/billing/dlq/cleanup-expired
   curl -X POST http://localhost:8000/api/v1/admin/cleanup-stale-jobs
   ```

## Prevention
- Run `celery-beat-standby` for HA (already in docker-compose)
- Monitor `workticket_beat_lock_skipped_total` metric
