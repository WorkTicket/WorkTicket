# Tenant Isolation Model

## Overview

WorkTicket is a multi-tenant SaaS platform. Every operation is scoped to a `company_id`. Tenant isolation is enforced at three layers:

1. **Application Layer** — All SQL queries include `company_id` filters via SQLAlchemy scoping
2. **Database Layer** — PostgreSQL Row-Level Security (RLS) provides a defense-in-depth barrier
3. **API Layer** — JWT claims are verified and `company_id` is extracted from the authenticated token

## Tenant Context Flow

```
Request → Clerk JWT → Extract company_id → Tenant Context Middleware → Scoped Query → RLS Filtered Result
```

The `company_id` is injected into every request via a `ContextVar` in `app/db/tenant_context.py`. All repository-level queries filter on this value. RLS policies on every table enforce the same constraint at the database level.

## Row-Level Security

RLS is enabled on all tenant-scoped tables via migration `027_enable_row_level_security.py`. Each table has a policy:

```sql
CREATE POLICY tenant_isolation ON <table>
  FOR ALL
  USING (company_id = current_setting('app.current_company_id')::uuid);
```

The `app.current_company_id` setting is set at the start of each database session via `app/db/rls.py`.

## Company ID Scoping

All models inherit from `TenantMixin` which adds `company_id` as a foreign key. Queries automatically scope via:

- SQLAlchemy event listeners that inject `company_id` on `before_select`
- Explicit `WHERE company_id = :company_id` in all custom SQL
- RLS as a backstop for any missed query paths

## Verified Isolation Paths

The following resources are verified tenant-isolated in tests:

- Jobs (list, get by ID, create, update, delete)
- Media (upload, access by ID)
- Customers (CRUD, list)
- Quotes (get by ID, list)
- Estimates (get by ID, list)
- Billing accounts (access, modification)
- AI metrics and outputs
- Analytics data
- Push tokens
- Invoices

## Test Coverage

See `tests/security/test_tenant_isolation.py` for 20+ cross-tenant isolation tests covering all resource types.
