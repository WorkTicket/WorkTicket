# DB Saturation Runbook

## Symptoms
- `workticket_db_pool_utilization_pct > 80%`
- `DBCircuitBreakerOpen` alert
- API requests returning 503 with "Database connection pool exhausted"
- Slow query response times

## Steps

### 1. Identify long-running queries
```sql
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle'
  AND now() - pg_stat_activity.query_start > interval '5 seconds'
ORDER BY duration DESC;
```

### 2. Cancel stuck queries
```sql
SELECT pg_cancel_backend(pid);
```

If cancel doesn't work:
```sql
SELECT pg_terminate_backend(pid);
```

### 3. Scale pool size temporarily
Adjust `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` in environment:
```
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=20
```
Restart the affected service (API, worker, or beat) after changing.

### 4. Check for deadlocks
```sql
SELECT * FROM pg_locks WHERE NOT granted;
```

### 5. Verify recovery
- Check `workticket_db_pool_utilization_pct` drops below 60%
- Check circuit breaker is closed: `workticket_db_pool_circuit_breaker == 0`
- Verify API returns 200 on `/healthz`

## Prevention
- Add missing indexes (run `EXPLAIN ANALYZE` on slow queries)
- Increase `db_pool_size` in config if sustained load exceeds capacity
- Implement query timeouts at the application level
