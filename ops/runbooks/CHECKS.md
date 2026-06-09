# Pre-Deploy Checklist

## Required Configuration

- [ ] `WS_ENABLED=true` in environment
- [ ] `CELERY_TASK_SIGNING_KEY` set to strong random value (256-bit hex)
- [ ] Redis `maxmemory >= 1GB` (broker) and `>= 200MB` (cache)
- [ ] Redis `maxmemory-policy noeviction` (broker)
- [ ] `DB_POOL_SIZE >= 25` in config
- [ ] `PG_POOL_SIZE >= 35` in PgBouncer
- [ ] `METRICS_ACCESS_TOKEN` set

## Pre-Deploy Verification

- [ ] All beat tasks ran successfully at least once in staging
- [ ] Stripe webhook endpoint verified (IP cache populated)
- [ ] Prometheus alerts configured and firing in staging
- [ ] Grafana dashboards load correctly with staging data
- [ ] Alembic migrations run and verified
- [ ] Rollback plan documented
- [ ] `/readyz` returns 200 for all components

## Post-Deploy Verification

- [ ] `/livez` returns 200
- [ ] `/readyz` returns 200 for all components
- [ ] Celery workers ping successfully
- [ ] WebSocket connections accepted (`workticket_ws_enabled == 1`)
- [ ] Stripe webhook endpoint responds 200
- [ ] No 503 errors in logs
- [ ] Queue depths stable
- [ ] DB pool utilization < 60%

## Rollback Criteria

If any of the following are observed within 15 minutes of deploy:
- Error rate increase > 5%
- 503 rate > 1%
- DB pool utilization > 80%
- Circuit breaker opens
- Customer-reported issues

**Initiate rollback immediately.**
