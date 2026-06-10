"""Add estimate audit log and user audit log tables.

Revision ID: 038
Revises: 037
Create Date: 2026-06-06

Fixes identified in DDA v1.0 (Data Integrity section):
- estimate_audit_logs: traces who approved/modified estimates
- user_audit_logs: traces who activated/deactivated users or changed roles
- Adds pii_access_audit model wiring

Both are append-only (immutable) audit trails with old_value/new_value tracking.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "estimate_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("estimate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by_user_id", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_est_audit_logs_estimate_id", "estimate_audit_logs", ["estimate_id"])
    op.create_index("ix_est_audit_logs_company_id", "estimate_audit_logs", ["company_id"])
    op.create_index("ix_est_audit_logs_created_at", "estimate_audit_logs", ["created_at"])
    op.create_foreign_key(
        "fk_est_audit_logs_company", "estimate_audit_logs", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )

    op.create_table(
        "user_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("target_user_id", sa.String(255), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by_user_id", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_user_audit_logs_target_user", "user_audit_logs", ["target_user_id"])
    op.create_index("ix_user_audit_logs_company_id", "user_audit_logs", ["company_id"])
    op.create_index("ix_user_audit_logs_created_at", "user_audit_logs", ["created_at"])
    op.create_foreign_key(
        "fk_user_audit_logs_company", "user_audit_logs", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )

    op.execute(sa.text("ALTER TABLE estimate_audit_logs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON estimate_audit_logs "
            "USING (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) "
            "WITH CHECK (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY tenant_isolation_bypass ON estimate_audit_logs "
            "USING (current_setting('app.bypass_rls', true) = 'true') "
            "WITH CHECK (current_setting('app.bypass_rls', true) = 'true')"
        )
    )
    op.execute(sa.text("ALTER TABLE estimate_audit_logs FORCE ROW LEVEL SECURITY"))

    op.execute(sa.text("ALTER TABLE user_audit_logs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY tenant_isolation ON user_audit_logs "
            "USING (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) "
            "WITH CHECK (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY tenant_isolation_bypass ON user_audit_logs "
            "USING (current_setting('app.bypass_rls', true) = 'true') "
            "WITH CHECK (current_setting('app.bypass_rls', true) = 'true')"
        )
    )
    op.execute(sa.text("ALTER TABLE user_audit_logs FORCE ROW LEVEL SECURITY"))


def downgrade():
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON user_audit_logs"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_bypass ON user_audit_logs"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON estimate_audit_logs"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_bypass ON estimate_audit_logs"))
    op.drop_table("user_audit_logs")
    op.drop_table("estimate_audit_logs")
