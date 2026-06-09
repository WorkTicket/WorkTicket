# ADR 007: Database Connection Pool Architecture

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket uses PostgreSQL 16 with PgBouncer for connection pooling. The
application runs multiple services (FastAPI backend, 5 Celery worker types,
Celery beat) that all need database access. Without careful pool sizing,
connection exhaustion is a real risk with PostgreSQL's default max_connections=100.

## Decision

### Pool Architecture
| Component | Pool Size | Max Overflow | Total Max |
|-----------|-----------|-------------|-----------|
| FastAPI (main) | 25 | 10 | 35 |
| FastAPI (readonly) | 25 | 10 | 35 |
| Celery workers (shared) | 5 | 2 | 7 |
| Celery beat | 25 | 10 | 35 |

### PgBouncer Configuration
- **Mode**: Transaction pooling
- **Max client connections**: 150
- **Default pool size**: 50
- **Reserve pool size**: 10
- **Reserve pool timeout**: 5s

### Connection Protection Mechanisms
1. **Circuit breaker**: Opens when pool utilization exceeds 85% or 3
   consecutive errors occur. Redis-coordinated across replicas.
2. **Statement timeout**: 30s per statement (prevents long-running queries
   from holding connections)
3. **PgBouncer transaction mode**: Connections are returned to the pool
   after each transaction, not each session
4. **Pool pre-ping**: Validates connections before use
5. **LIFO pool strategy**: Reuses most recently released connections
   (better cache locality)

## Consequences

- **Stable under load**: Circuit breaker prevents cascading failures
- **Connection budget respected**: Total max connections ~112, well
  under PostgreSQL's max_connections=100
- **Read replica support**: Separate engine/pool for read replicas
  prevents analytics from impacting write performance
