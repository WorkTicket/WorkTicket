# Performance Baseline

WorkTicket production performance targets, SLI definitions, and monitoring strategy.

## SLI / SLO Summary

| SLI | Target | Measurement Window | Alert Threshold |
|-----|--------|-------------------|-----------------|
| API availability | 99.9% | 5m rolling | 5xx > 0.1% |
| Latency P95 | 500ms | 5m rolling | > 750ms warning, > 1s critical |
| Latency P99 | 2000ms | 5m rolling | > 3s critical |
| Error rate | 0.1% | 5m rolling | > 0.5% warning, > 1% critical |
| DB availability | 99.95% | 5m rolling | Pool exhausted, circuit open |
| Redis availability | 99.95% | 5m rolling | Rate limiter fallback detected |
| Celery queue health | 99% | 5m rolling | Depth > threshold per queue |
| AI availability | 95% | 5m rolling | Fallback rate > 5% |
| Webhook processing | 99.9% | 5m rolling | P999 > 10s, DLQ growing |

## Latency Targets by Endpoint Class

| Tier | Endpoint Classes | P95 Target | Warning | Critical |
|------|-----------------|-----------|---------|----------|
| **Critical** | Job creation, billing, checkout, webhooks | < 200ms | > 300ms | > 500ms |
| **Normal** | Quotes, estimates, media upload, customer lookups | < 1s | > 1.5s | > 2s |
| **Report** | Analytics, metrics, exports, admin queries | < 5s | > 7.5s | > 10s |

### Critical Endpoints
- `POST /api/v1/jobs` — job creation
- `POST /api/v1/billing/checkout` — Stripe checkout
- `POST /api/v1/billing/webhook` — Stripe webhook ingestion
- `GET /api/v1/jobs/{id}/status` — job status poll (real-time consumers)
- `POST /api/v1/billing/quota-reset` — monthly billing reset

### Normal Endpoints
- `POST /api/v1/quotes` — quote generation
- `POST /api/v1/estimates` — labor/material estimates
- `POST /api/v1/media/upload` — image/audio upload
- `GET /api/v1/customers/{id}` — customer profile lookup
- `POST /api/v1/ai/predict` — AI inference (non-streaming)
- `GET /api/v1/inventory/search` — parts/inventory search

### Report Endpoints
- `GET /api/v1/analytics/jobs` — job analytics dashboard
- `GET /api/v1/analytics/revenue` — revenue reports
- `GET /api/v1/exports/jobs` — CSV/PDF job exports
- `GET /api/v1/metrics/performance` — internal performance metrics
- `GET /api/v1/admin/audit-log` — admin audit log queries

## Database Performance

### Slow-Query Thresholds

| Threshold | Action | Metric Source |
|-----------|--------|---------------|
| > 500ms | Log query plan + parameters | `pg_stat_statements` via `workticket_db_p99_latency_ms` |
| > 2s | Alert via Prometheus | `workticket_db_slow_query_count` |
| > 5s | Page on-call | Escalation from alert |

### pg_stat_statements Monitoring

- **Review cadence**: Daily during standup
- **Dashboard**: Grafana "Database" row in `workticket-slos`
- **Key metrics to watch**:
  - `mean_exec_time` — average per-query execution time
  - `calls` — execution frequency to catch N+1 patterns
  - `shared_blks_hit / shared_blks_read` — cache hit ratio per query
  - `rows` — row scan volume to detect missing indexes
- **Extension**: Ensure `pg_stat_statements` is enabled (`shared_preload_libraries` in postgresql.conf)
- **Retention**: `pg_stat_statements.max = 10000` (default), reset via `SELECT pg_stat_statements_reset()` after analysis

### PgBouncer Monitoring

| Metric | Target | Source |
|--------|--------|--------|
| Pool utilization | < 70% | `workticket_pgbouncer_queue_depth` |
| Idle-in-transaction | 0 | `workticket_pgbouncer_idle_in_txn` |
| Client wait time | < 1ms | PgBouncer stats |

## Load Test Profile

| Parameter | Value |
|-----------|-------|
| Concurrent users | 50 |
| Job creation rate | 100 jobs/hour (~1.7/min) |
| Ramp-up time | 2 minutes |
| Steady state | 30 minutes |
| Think time | 5-15s between user actions |
| Target environment | Staging (never production) |

### User Journey Mix
1. Browse dashboard → view jobs (40%)
2. Create job + upload images (30%)
3. Request estimate from AI (20%)
4. Billing checkout flow (5%)
5. Admin analytics reports (5%)

### Acceptance Criteria
- P95 latency within tier targets under full load
- Zero 5xx errors during steady state
- No queue depth growth (tasks processed faster than generated)
- DB pool utilization stays below 70%
- Redis memory stays below 80%

## Alert Routing

| Severity | Channel | Response Time |
|----------|---------|---------------|
| Critical | PagerDuty + Slack #alerts-critical | 5 min |
| Warning | Slack #alerts-warning | 15 min |
| Info | Slack #alerts-info | Next business day |

## Related Documents

- `ops/performance/sli-mapping.md` — Detailed SLI-to-Prometheus-query mapping
- `ops/performance/latency-targets.md` — Per-endpoint latency classification
- `ops/grafana-dashboards/workticket-slos.json` — SLO dashboard definition
- `ops/prometheus-alerts/workticket-alerts.yml` — Alert rules
- `ops/adversarial-load-testing.md` — Chaos/load testing tooling
