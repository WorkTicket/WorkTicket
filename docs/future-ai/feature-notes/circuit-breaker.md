# Feature Note: Circuit Breaker & Concurrency Control

## Component Information

- **Name:** AI Circuit Breaker & Concurrency Limiter
- **Files:** 
  - `src/backend/app/ai/circuit_breaker.py`
  - `src/backend/app/ai/concurrency.py`
- **Dependencies:** Redis (for state and locks)
- **Env Vars:** None (uses Redis from Settings)
- **Infrastructure:** Redis

## Current Status

Circuit breaker protects the system from cascading failures when AI services (Ollama, Whisper) are unavailable. Uses Redis-backed global state with Lua scripts for atomic half-open probe coordination across replicas.

Concurrency limiter prevents over-commit of AI resources per company using Redis locks with TTL-based expiry.

**Production Readiness:** Production-ready
**Known Issues:** None
**Technical Debt:** Half-open probe timing may need tuning for cloud AI providers with different latency profiles

## Reactivation Plan

Automatically active when AI is enabled — no separate activation needed. Verify with:
```
GET /api/v1/ai/metrics  # Check circuit states
```

## Architecture Notes

Circuit breaker states: CLOSED (normal operation) → OPEN (tripped after threshold failures) → HALF_OPEN (probing recovery). Redis Lua scripts ensure only one replica enters HALF_OPEN at a time.
