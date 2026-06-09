# Full Outage Runbook

## Orderly Shutdown Sequence

1. **Stop accepting new traffic**
   ```bash
   # Remove backend from load balancer pool
   # Or set maintenance page
   curl -X POST http://localhost:8000/api/v1/admin/maintenance \
     -H "Content-Type: application/json" \
     -d '{"enabled": true}'
   ```

2. **Drain in-flight requests**
   - Wait for LB drain timeout (default 5s)
   - App shutdown waits up to 15s for in-flight requests
   - WebSocket connections get close frame with code 1000

3. **Stop Celery workers gracefully**
   ```bash
   docker compose stop celery-worker-beat
   docker compose stop celery-worker
   ```
   Workers wait up to 25s for active tasks to complete.

4. **Stop remaining services**
   ```bash
   docker compose down
   ```

## Recovery Sequence

1. **Check PostgreSQL**
   ```bash
   pg_isready -h localhost -p 5432
   psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
   ```

2. **Check Redis**
   ```bash
   redis-cli PING
   redis-cli INFO memory | grep used_memory_human
   redis-cli DBSIZE
   ```

3. **Start services**
   ```bash
   docker compose up -d postgres redis-broker redis-cache pgbouncer
   sleep 10
   docker compose up -d backend celery-beat celery-worker celery-worker-beat
   sleep 15
   docker compose up -d nginx
   ```

4. **Verify health**
   ```bash
   curl -f http://localhost:8000/livez
   curl -f http://localhost:8000/healthz
   curl -f http://localhost:8000/readyz
   ```

5. **Check queue processing**
   ```bash
   celery -A celery_app status
   redis-cli LLEN default
   ```

6. **Verify beat tasks resumed**
   ```bash
   docker logs --tail=10 workticket-celery-beat-1 | grep "Task cleanup"
   ```

## Post-Mortem Checklist
- [ ] Export logs from all services
- [ ] Capture Redis RDB snapshot
- [ ] Capture DB `pg_stat_statements` snapshot
- [ ] Check Sentry for error spike
- [ ] Review alert firing timeline
