# Per-Endpoint Latency Classification

Every API endpoint is assigned a criticality tier that determines its SLO target, alerting thresholds, and dashboard grouping.

## Tier Definitions

| Tier | P95 Target | Warning | Critical | Description |
|------|-----------|---------|----------|-------------|
| **Critical** | < 200ms | > 300ms | > 500ms | Revenue-affecting or real-time user flows |
| **Normal** | < 1s | > 1.5s | > 2s | Core business logic, non-revenue-critical |
| **Report** | < 5s | > 7.5s | > 10s | Analytical/administrative queries, exports |

## Critical Tier — P95 < 200ms

These endpoints are on the hot path for user acquisition and payment. Degradation here directly impacts revenue.

| Method | Path | Description | DB Queries (target) |
|--------|------|-------------|---------------------|
| `POST` | `/api/v1/jobs` | Create work ticket job | ≤ 3 |
| `GET` | `/api/v1/jobs/{id}/status` | Poll job status (WS fallback) | ≤ 1 |
| `POST` | `/api/v1/billing/checkout` | Stripe checkout session create | ≤ 2 |
| `POST` | `/api/v1/billing/webhook` | Stripe webhook event ingest | ≤ 5 |
| `POST` | `/api/v1/billing/quota-reset` | Monthly ACU quota reset | ≤ 3 |

## Normal Tier — P95 < 1s

Standard API operations. Most user-facing endpoints fall here.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/quotes` | Generate labor/material quote |
| `POST` | `/api/v1/estimates` | AI-assisted estimate generation |
| `POST` | `/api/v1/media/upload` | Upload job images/audio |
| `GET` | `/api/v1/jobs` | List jobs (paginated) |
| `PATCH` | `/api/v1/jobs/{id}` | Update job details |
| `DELETE` | `/api/v1/jobs/{id}` | Cancel/delete job |
| `GET` | `/api/v1/customers/{id}` | Customer profile |
| `GET` | `/api/v1/customers` | Search customers |
| `POST` | `/api/v1/ai/predict` | AI inference (non-streaming) |
| `GET` | `/api/v1/inventory/search` | Parts/inventory search |
| `GET` | `/api/v1/notifications` | User notifications list |
| `POST` | `/api/v1/webhooks/register` | Register external webhook |
| `GET` | `/api/v1/plans` | List subscription plans |
| `GET` | `/api/v1/usage` | Current billing usage |
| `WS` | `/ws/{user_id}` | WebSocket upgrade (connection) |

## Report Tier — P95 < 5s

Heavy read queries, aggregation, and export endpoints. These are expected to be slow and should not block API workers.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/analytics/jobs` | Job volume/status analytics |
| `GET` | `/api/v1/analytics/revenue` | Revenue breakdown reports |
| `GET` | `/api/v1/analytics/customers` | Customer acquisition funnel |
| `GET` | `/api/v1/exports/jobs` | Export jobs to CSV/PDF |
| `GET` | `/api/v1/exports/billing` | Export billing history |
| `GET` | `/api/v1/metrics/performance` | Internal performance metrics |
| `GET` | `/api/v1/admin/audit-log` | Immutable audit log queries |
| `GET` | `/api/v1/admin/users` | Admin user management list |
| `GET` | `/api/v1/health` | Full health check (all deps) |
| `GET` | `/api/v1/health/lite` | Light health check (no DB) |

## Grafana Dashboard Panels

| Panel | Dashboard | Query |
|-------|-----------|-------|
| Latency Percentiles | `workticket-slos` → API Health | `histogram_quantile(0.50/0.95/0.99, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le))` |
| By Endpoint Class | `workticket-slos` → API Health | `histogram_quantile(0.95, sum(rate(workticket_http_request_duration_seconds_bucket[5m])) by (le, endpoint_class))` |
| Latency Budget | `workticket-slos` → API Health | `sum(rate(bucket{le="<target>"}[5m])) / sum(rate(_count[5m]))` per tier |
| Slow Query Count | `workticket-slos` → API Health | `rate(pg_stat_statements_mean_time_seconds{quantile="0.99"}[5m])` |

## HTTP Middleware: Latency Measurement

The `workticket_http_request_duration_seconds` histogram records every HTTP request with labels:

```
workticket_http_request_duration_seconds_bucket{
    method="POST",
    path="/api/v1/jobs",
    endpoint_class="critical",
    status="201",
    le="0.1"
}
```

The `endpoint_class` label is set by middleware matching `path` prefixes:
- `critical`: paths matching `/api/v1/jobs`, `/api/v1/billing/`
- `normal`: paths matching `/api/v1/quotes`, `/api/v1/estimates`, `/api/v1/media`, `/api/v1/customers`, `/api/v1/ai`, `/api/v1/inventory`, `/api/v1/notifications`, `/api/v1/webhooks`, `/api/v1/plans`, `/api/v1/usage`, `/ws`
- `report`: paths matching `/api/v1/analytics`, `/api/v1/exports`, `/api/v1/metrics`, `/api/v1/admin`, `/api/v1/health`

## Performance Testing Verification

Each latency target is validated during load testing:

```bash
# Run load test against staging
python -m locust -f tests/load/locustfile.py \
  --host https://staging.example.com \
  --users 50 \
  --spawn-rate 5 \
  --run-time 30m \
  --headless \
  --csv results/

# Verify per-endpoint-class P95 after test
jq '.[] | select(.name | startswith("/api/v1/")) | {name, p95: .latency.p95}' results/*_stats.json
```
