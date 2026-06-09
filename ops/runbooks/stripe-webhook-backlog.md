# Stripe Webhook Backlog Runbook

## Symptoms
- `StripeCircuitBreakerOpen` alert firing
- Webhook processing latency > 10s
- Billing drift > 5%

## Detection
```bash
# Check circuit breaker state
curl http://localhost:8000/api/v1/billing/stripe/circuit

# Check webhook processing rate
redis-cli GET "stripe:webhook:concurrent"

# Check DLQ for webhook entries
curl http://localhost:8000/api/v1/billing/dlq/stats
```

## Steps

1. **Check Stripe API status**
   ```bash
   curl -I https://api.stripe.com/v1/health
   ```

2. **If circuit breaker is open**
   The circuit automatically half-opens after `CIRCUIT_COOLDOWN` (30s).
   To force-reset:
   ```bash
   redis-cli DEL "stripe:circuit_breaker"
   ```

3. **Clear webhook backlog**
   ```bash
   # Check pending webhooks in Stripe dashboard
   # Replay from Stripe: Settings → Webhooks → Failed deliveries → Replay
   
   # Or re-fetch recent events via API
   curl -X POST http://localhost:8000/api/v1/billing/webhook/replay \
     -H "Content-Type: application/json" \
     -d '{"hours_back": 1}'
   ```

4. **Verify billing consistency**
   ```bash
   curl http://localhost:8000/api/v1/billing/reconciliation/drift
   ```

## Prevention
- Global webhook concurrency cap at 5
- Redis-based webhook ID dedup
- Stripe IP cache refreshed every 30 min
- Monitor `workticket_stripe_circuit_state` gauge
