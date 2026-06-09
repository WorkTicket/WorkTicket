"""Fix RLS policies: strict tenant isolation + WITH CHECK.

Revision ID: 033
Revises: 032
Create Date: 2026-06-05

Fixes identified in security audit:
1. Removes auto-bypass: NULL/empty tenant_id now blocks all queries
   (instead of showing all rows), closing cross-tenant data access.
2. Adds explicit WITH CHECK clauses for INSERT/UPDATE enforcement.
3. Bypass policy requires explicit SET app.bypass_rls = 'true',
   preventing accidental cross-tenant access from internal operations.
"""

import sqlalchemy as sa

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None

_TENANT_SCOPED_TABLES = [
    "users",
    "customers",
    "jobs",
    "job_media",
    "ai_outputs",
    "quotes",
    "billing_accounts",
    "usage_ledger",
    "invoices",
    "company_pricing_brains",
    "services",
    "estimates",
    "estimate_line_items",
    "historical_job_data",
    "ai_job_estimates",
    "notifications",
    "push_tokens",
    "analytics_events",
    "companies",
]


def upgrade():
    conn = op.get_bind()

    for table in _TENANT_SCOPED_TABLES:
        result = conn.execute(
            sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'company_id'
        """),
            {"table": table},
        )
        if not result.fetchone():
            continue

        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}"))

        if table == "companies":
            conn.execute(
                sa.text(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING (id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) "
                    f"WITH CHECK (id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
                )
            )
        else:
            conn.execute(
                sa.text(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) "
                    f"WITH CHECK (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
                )
            )

        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation_bypass ON {table} "
                f"USING (current_setting('app.bypass_rls', true) = 'true') "
                f"WITH CHECK (current_setting('app.bypass_rls', true) = 'true')"
            )
        )

    conn.execute(
        sa.text(
            "DO $$ BEGIN   EXECUTE 'ALTER DATABASE ' || current_database() ||   ' SET app.bypass_rls TO '''' '; END $$"
        )
    )


def downgrade():
    conn = op.get_bind()

    for table in reversed(_TENANT_SCOPED_TABLES):
        result = conn.execute(
            sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'company_id'
        """),
            {"table": table},
        )
        if not result.fetchone():
            continue

        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}"))

        if table == "companies":
            conn.execute(
                sa.text(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING (id = COALESCE(NULLIF(current_setting('app.current_tenant_id', true), '')::uuid, id))"
                )
            )
        else:
            conn.execute(
                sa.text(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING (company_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', true), '')::uuid, company_id))"
                )
            )

        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation_bypass ON {table} "
                f"USING (NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL) "
                f"WITH CHECK (NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL)"
            )
        )

        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
