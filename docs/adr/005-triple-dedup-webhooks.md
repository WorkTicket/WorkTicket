# ADR 005: Triple-Dedup Webhook Processing

**Status:** Accepted
**Date:** 2026-06-05

## Context

Stripe webhooks are critical for payment processing. A duplicate webhook
could result in double-charging customers, double-crediting accounts,
or incorrect subscription state. Stripe guarantees at-least-once delivery
but does not guarantee exactly-once delivery.

We need to ensure every Stripe webhook event is processed **exactly once**,
even under concurrent delivery, network retries, and Redis failures.

## Decision

We implement **three layers of deduplication**:

### Layer 1: PostgreSQL INSERT ON CONFLICT DO NOTHING (Primary)
- `StripeWebhookEvent` table has a unique constraint on `stripe_event_id`
- `INSERT ... ON CONFLICT (stripe_event_id) DO NOTHING` ensures at-most-once
  processing at the database level
- This is the authoritative dedup layer

### Layer 2: Redis SET NX with 7-day TTL (Fast-path)
- Before attempting DB insert, check Redis for `webhook_dedup:{event_id}`
- If key exists, reject immediately (already processed)
- 7-day TTL matches Stripe's maximum retry window
- Provides sub-millisecond dedup without DB round-trip

### Layer 3: PostgreSQL Advisory Lock (Tertiary)
- `pg_try_advisory_xact_lock(hashtext(event_id))` as a last-resort dedup
- Handles race conditions where Redis is unavailable and two concurrent
  requests both pass the Redis check but hit the DB simultaneously
- Transaction-scoped: lock is released on commit/rollback

## Consequences

- **Triple protection** against duplicate processing
- **Minimal latency**: Fast path (Redis) handles 99.9% of cases
- **No dependency on single component**: Works even if Redis is down
- **Additional DB overhead**: Extra advisory lock acquisition per webhook
