# ADR 008: Circuit Breaker Pattern for External Services

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket depends on multiple external services (Stripe, Ollama AI,
faster-whisper, Resend email, Twilio SMS). When these services fail
or become slow, retry amplification can:
- Exhaust database connection pools
- Saturate Celery queues with failing tasks
- Cause cascading failures across internal services
- Delay responses for unrelated requests

## Decision

We implement the **circuit breaker pattern** for all external service
dependencies, with three states:

### States
1. **CLOSED**: Normal operation. Requests flow through normally.
2. **OPEN**: Service is failing. Requests are rejected immediately
   (fast-fail) without calling the external service.
3. **HALF-OPEN**: Cooldown period expired. Exactly 1 probe request
   is allowed to test if the service has recovered.

### Configuration (per service)

| Service | Failure Threshold | Cooldown (base) | Max Cooldown |
|---------|-------------------|-----------------|-------------|
| Stripe | 3 failures | 120s | 600s |
| Ollama (LLM) | 3 failures | 60s | 300s |
| Whisper (audio) | 3 failures | 60s | 300s |
| Resend (email) | 3 failures | 120s | 600s |
| Twilio (SMS) | 3 failures | 120s | 600s |
| Redis Broker | 3 failures | 30s | 300s |
| PostgreSQL | 3 errors / 85% pool | 30s | 300s |

### Redis Coordination
- Database and Redis broker circuits use Redis Lua scripts for
  atomic state transitions across all replicas
- Prevents split-brain where one replica opens the circuit while
  another keeps sending requests

## Consequences

- **Fast failure**: Services degrade gracefully instead of hanging
- **Automatic recovery**: Half-open probes detect service restoration
- **Exponential backoff**: Cooldown doubles each time the circuit opens
  (30s → 60s → 120s → 300s), preventing oscillation
