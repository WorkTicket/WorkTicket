# Runbook: Redis Outage

## Impact
- Rate limiter falls back to in-memory token bucket (local mode)
- Rate limiting accuracy degrades (per-process, not shared)
- Celery tasks continue using broker Redis (separate instance if configured)
- **No 503 errors from rate limiting** — graceful degradation

## Detection
- `/readyz` → `components.rate_limiter.mode` = `local`
- Alert: `rate_limiter_fallback_active` metric > 0
- Logs: "Redis unavailable for rate limiter" (WARNING)

## Recovery
1. Check Redis process: `docker-compose ps redis`
2. Check Redis logs: `docker-compose logs redis`
3. Restart Redis if needed: `docker-compose restart redis`
4. Verify recovery: `/readyz` → `components.rate_limiter.mode` = `redis`

## Emergency Override
- Set `RATE_LIMITER_FAIL_OPEN=true` to force in-memory mode
- Set `STRIPE_WEBHOOK_IP_CHECK_DISABLED=1` to skip IP checks
