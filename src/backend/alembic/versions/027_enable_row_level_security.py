"""Enable PostgreSQL Row-Level Security on all tenant-scoped tables.

Revision ID: 027
Revises: 026
Create Date: 2026-06-05

Enables RLS on all 19 tenant-scoped tables as defense-in-depth for tenant
isolation. Each table gets a tenant_isolation policy that restricts rows
to those matching the current tenant ID set via:
    SET app.current_tenant_id = '<company_id>';

A bypass policy is also created for internal/system operations where no
tenant context is set.
"""

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
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
        # Check if table has a company_id column
        result = conn.execute(
            sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'company_id'
        """),
            {"table": table},
        )
        if not result.fetchone():
            continue

        # Enable RLS
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

        # Drop existing policy if any (for idempotent re-runs)
        conn.execute(sa.text(f"DO $$ BEGIN   DROP POLICY IF EXISTS tenant_isolation ON {table}; END $$"))

        # Drop bypass policy if any
        conn.execute(sa.text(f"DO $$ BEGIN   DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}; END $$"))

        # Create tenant isolation policy
        if table == "companies":
            # For companies table, the company_id column IS the id column
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

        # Create bypass policy for operations without tenant context
        # This allows internal/system operations that don't have a tenant set
        conn.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation_bypass ON {table} "
                f"USING (NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL)"
                f"  WITH CHECK (NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL)"
            )
        )

        # Force RLS for table owner (prevent BYPASSRLS privilege bypass)
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    # Create the custom GUC variable for passing tenant ID
    conn.execute(
        sa.text(
            "DO $$ BEGIN "
            "  EXECUTE 'ALTER DATABASE ' || current_database() || "
            "  ' SET app.current_tenant_id TO '''' '; "
            "END $$"
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

        conn.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"  DROP POLICY IF EXISTS tenant_isolation ON {table}; "
                f"  DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}; "
                f"END $$"
            )
        )
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
