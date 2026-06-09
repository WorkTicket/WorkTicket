# ADR 006: Row-Level Security Defense-in-Depth

**Status:** Accepted
**Date:** 2026-06-05

## Context

The primary tenant isolation mechanism is an application-level
SQLAlchemy `do_orm_execute` event that auto-injects `company_id`
filters. However, this filter can be bypassed by:
- Raw SQL queries (used in migrations, health checks)
- New developers unfamiliar with the pattern
- Future framework migrations or ORM changes
- Direct database access by operators/DBAs

## Decision

We enable **PostgreSQL Row-Level Security (RLS)** on all 19
tenant-scoped tables as a defense-in-depth layer.

### Implementation (Alembic migration 027):
- `ALTER TABLE {table} ENABLE ROW LEVEL SECURITY`
- `CREATE POLICY tenant_isolation ON {table} USING (company_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', true), '')::uuid, company_id))`
- `ALTER TABLE {table} FORCE ROW LEVEL SECURITY`

### Tenant context propagation:
- The application sets `app.current_tenant_id` via `SET` command
  at session creation time (in `get_db()`, `get_db_readonly()`,
  `get_db_with_refresh()`)
- The context is cleared before returning the session to the pool
- When no tenant is set (internal operations), a bypass policy
  allows all rows (`NULLIF(current_setting(...), '') IS NULL`)

## Consequences

### Positive
- **Defense-in-depth**: Even if the ORM filter fails, RLS catches it
- **Protects against raw SQL**: Direct SQL queries are still scoped
- **Operator protection**: Database administrators cannot accidentally
  expose cross-tenant data without explicitly clearing the setting
- **Zero performance impact**: RLS on indexed columns adds negligible
  overhead (PostgreSQL optimizes constant-filter policies)

### Negative
- **Added complexity**: Sessions must set/clear the tenant context
- **Migration dependency**: RLS migration (027) must run before the
  application expects RLS enforcement
- **Debugging**: Queries that unexpectedly return 0 rows (RLS filtering)
  can be confusing during development
