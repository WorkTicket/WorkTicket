# Runbook: Stripe Webhook Failure

## Detection
- Webhook 403 rate > 0 (Stripe IPs changed)
- Invoice not created for completed checkout
- Customer paid but not upgraded

## Investigation
1. Check Stripe dashboard for webhook delivery status
2. Check `/readyz` → `components.stripe_ip_cache`
3. Check logs: "Webhook request from non-Stripe IP" (WARNING)

## Recovery
1. Force refresh Stripe IPs: restart backend or hit management endpoint
2. Manually replay webhook from Stripe dashboard
3. If emergency: set `STRIPE_WEBHOOK_IP_CHECK_DISABLED=1`

## Manual Compensations
- Find affected customers: check `stripe_webhook_events` table
- Manually upgrade: `UPDATE companies SET subscription_plan='pro' WHERE id='...'`
- Manually create invoice if missing
