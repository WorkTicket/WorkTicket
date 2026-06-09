# DB Saturation Runbook

## Detection
- Alert: `DBCircuitBreakerOpen` or `DBPoolHighUtilization`
- Symptom: 503 responses, slow queries, connection timeouts

## Triage
1. Check pool utilization: `workticket_db_pool_utilization_pct`
2. Check circuit breaker state: `workticket_db_pool_circuit_breaker`
3. Identify hogging queries: `SELECT * FROM pg_stat_activity ORDER BY state_change DESC`
4. Check PgBouncer stats: `SHOW STATS; SHOW POOLS;`

## Mitigation
1. **Immediate**: Kill long-running queries: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 minutes'`
2. **Pool resize**: Temporarily increase `pool_size` and `max_overflow` in config
3. **Load shed**: The circuit breaker will auto-reject new requests to allow recovery
4. **Scale up**: Add more Celery workers or API replicas

## Recovery
1. Monitor pool utilization dropping below 60%
2. Circuit breaker will auto-close (exponential backoff with half-open probe)
3. Verify /readyz returns 200
4. Investigate root cause of the spike
