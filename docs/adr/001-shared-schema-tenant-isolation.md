# ADR 001: Shared Schema Multi-Tenant Isolation

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket is a multi-tenant SaaS platform serving HVAC and trade companies.
Each company (tenant) stores jobs, customers, quotes, invoices, and AI outputs
in a single shared PostgreSQL database. The primary security requirement is
that no tenant can ever access another tenant's data.

We evaluated three isolation models:
1. **Database-per-tenant** (separate PostgreSQL databases)
2. **Schema-per-tenant** (separate PostgreSQL schemas)
3. **Shared schema with discriminator column** (company_id on every table)

## Decision

We implemented **shared schema with company_id discriminator** for the beta
phase, with two complementary isolation layers:

1. **Application-level**: SQLAlchemy `do_orm_execute` event listener that
   auto-injects `company_id = current_tenant_id` into all SELECT/UPDATE/DELETE
   queries on 19 tenant-scoped tables. The tenant context is set via FastAPI
   dependency injection using Clerk JWT authentication.

2. **Database-level**: PostgreSQL Row-Level Security (RLS) policies as
   defense-in-depth (added in Alembic migration 027). Each tenant-scoped
   table has a policy: `USING (company_id = current_setting('app.current_tenant_id')::uuid)`.

### Why not database-per-tenant?
- Operational complexity of managing 100s of databases
- Higher connection pool overhead
- Cross-tenant reporting/analytics becomes complex

### Why not schema-per-tenant?
- Alembic migration complexity across 100s of schemas
- Connection pooling per-schema overhead
- Similar connection management challenges

## Consequences

### Positive
- Simple deployment: single database to manage
- Efficient connection pooling with PgBouncer
- Cross-tenant analytics are straightforward
- Migration management is simple (single schema)

### Negative
- **Hot tenant risk**: A single large tenant can saturate DB resources,
  impacting all other tenants. Mitigated by per-company quotas, billing
  enforcement, and query timeouts (30s statement_timeout).
- **Isolation bug impact**: A bug in the ORM filter or RLS policy could
  expose cross-tenant data. Risk reduced by having two independent
  isolation layers and comprehensive test coverage.
- **Scaling ceiling**: At ~1000+ tenants, we expect to need sharding or
  tenant-dedicated database instances.

### Migration Path
At scale (1000+ tenants), the architecture should evolve to:
1. Tenant-dedicated read replicas for large tenants
2. Horizontal sharding by company_id ranges
3. Eventually, dedicated databases for enterprise tenants
