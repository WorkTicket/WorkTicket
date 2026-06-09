"""Enable RLS on tables missing from migration 033.

Revision ID: 036
Revises: 033
Create Date: 2026-06-06

Fixes identified in security audit (DDA v1.0):
- 4 tables added after the original RLS migration (027) were never
  given row-level security policies:
  - idempotency_keys (added in migration 029)
  - job_audit_logs (added in migration 030)
  - billing_audit_logs (added in migration 030)
  - ai_output_feedback (company_id added in migration 032)

Also adds execution_traces to both RLS and ORM tenant scoping
(same strict policy from migration 033 — nil UUID block by default).
"""

import sqlalchemy as sa

from alembic import op

revision = "036"
down_revision = "033"
branch_labels = None
depends_on = None

_NEW_RLS_TABLES = [
    "idempotency_keys",
    "job_audit_logs",
    "billing_audit_logs",
    "ai_output_feedback",
    "execution_traces",
]


def upgrade():
    conn = op.get_bind()

    for table in _NEW_RLS_TABLES:
        result = conn.execute(
            sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table AND column_name = 'company_id'
        """),
            {"table": table},
        )
        if not result.fetchone():
            continue

        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}"))

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

        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def downgrade():
    conn = op.get_bind()

    for table in reversed(_NEW_RLS_TABLES):
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
        conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
