# Chaos Testing Guide

## Overview

Chaos tests validate system resilience under failure conditions. Run in **staging** only. Tests are located in `chaos/` and are designed to be non-destructive.

## Test Suite

| Test | Script | What It Validates |
|------|--------|-------------------|
| Redis Failover | `redis_failover.py` | Graceful degradation during 15min Redis outage, queue-depth backpressure, full recovery |
| Connection Spike | `connection_spike.py` | DB circuit breaker exponential backoff, half-open probe, oscillation elimination |
| Billing Contention | `billing_contention.py` | `skip_locked` on webhook handlers, billing reconciliation lock, lock contention metrics |
| Webhook Flood | `simulate_webhook_flood.py` | Redis dedup survival after crash, PG audit trail, idempotent retry |
| Celery Worker Kill | `celery_worker_kill.py` | PID-based DLQ fallback files, merge collector task, file rotation at 100MB |

## Pre-requisites

- Staging environment fully deployed with Docker Compose
- Prometheus + Grafana accessible
- `STRIPE_WEBHOOK_SECRET` set to `whsec_test_secret` for mock webhooks
- Redis and PostgreSQL containers named as `workticket-redis-broker-1` / `workticket-postgres-1`

## Running Tests

```bash
# Run a single test
python chaos/redis_failover.py

# Run all tests sequentially
python chaos/run_all.py
```

Results are written to `chaos/chaos_report.json`.

## Interpreting Results

Each test produces JSON output with a `passed` boolean and detailed metrics. Key signals:

- **Circuit breaker**: cooldown trace should show 30s → 60s → 120s → 300s (capped), never dropping back
- **Redis dedup**: retry of the same event IDs should all produce 200 (not 409/503)
- **DLQ fallback**: PID-named files created during outage, merged into main file after recovery

## Post-Test Cleanup

If a test leaves a container stopped, restart it manually:

```bash
docker start workticket-postgres-1
docker start workticket-redis-broker-1
```

## Adding New Tests

1. Create a new `.py` file in `chaos/` following the existing pattern
2. Accept configuration via environment variables
3. Return JSON output with `passed: bool` and relevant metrics
4. Add to `TESTS` list in `run_all.py`
