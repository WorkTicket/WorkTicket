# Stripe Webhook Failure Runbook

## Detection
- Symptom: Stripe dashboard shows failed webhook deliveries
- Alert: `workticket_stripe_webhook_lock_contention_total` > 10 in 5m
- Internal: 502/503 from /api/v1/billing/webhook

## Triage
1. Check Stripe dashboard for failed webhook attempts
2. Check DB audit: `SELECT * FROM stripe_webhook_events ORDER BY created_at DESC LIMIT 20`
3. Check circuit breaker state: `/readyz` components
4. Check Redis dedup: `redis-cli KEYS "stripe:dedup:*"`

## Manual Reconciliation
```sql
-- Find companies with unpaid subscriptions
SELECT c.id, c.company_name, c.stripe_subscription_id, c.subscription_plan
FROM companies c
LEFT JOIN billing_accounts ba ON ba.company_id = c.id
WHERE c.stripe_subscription_id IS NOT NULL
  AND c.subscription_plan = 'free'
  AND ba.plan != 'free';

-- Manually upgrade a company
UPDATE companies SET subscription_plan = 'pro', updated_at = NOW()
WHERE id = '<company_id>';
```

## Retry Procedure
1. In Stripe dashboard, manually retry the failed webhook
2. Verify Redis dedup key exists: `redis-cli GET stripe:dedup:<event_id>`
3. If event was lost, re-trigger from Stripe or manually reconcile

## Prevention
- Redis dedup prevents duplicate processing on retry
- PG dedup entries written after successful processing
- Startup-time Stripe IP cache population
