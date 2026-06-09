# Database Saturation Recovery

## Symptoms
- API returning 503 errors
- `/health` showing `db_pool_utilization > 80%`
- Slow queries timing out
- `pg_stat_activity` shows many `active` queries

## Immediate Actions

### 1. Identify Bad Queries
```sql
SELECT pid, now() - pg_stat_activity.query_start AS duration,
       query, state, wait_event
FROM pg_stat_activity
WHERE state = 'active'
  AND query NOT LIKE '%pg_stat_activity%'
  AND now() - pg_stat_activity.query_start > interval '30 seconds'
ORDER BY duration DESC;
```

### 2. Kill Blocking Connections
```sql
-- Find blocking locks
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
WHERE NOT blocked_locks.granted;

-- Kill the blocking connection
SELECT pg_terminate_backend(<blocking_pid>);
```

### 3. Check Pool Utilization
```bash
curl -s https://api.example.com/health | jq '.db_pool'
```

### 4. Scale Down
If circuit breaker is open, reduce incoming load:
```bash
docker compose up -d celery-worker-default --scale celery-worker-default=1
```

## Prevention
- Review slow query log after recovery
- Add missing indexes (check alembic migrations)
- Consider increasing PgBouncer pool size
- Review app code for N+1 queries
