"""Add immutable audit log tables for jobs and billing (D-1, R-1 fix).

Revision ID: 030
Revises: 029
Create Date: 2026-06-05

Creates job_audit_logs and billing_audit_logs tables for immutable
audit trails. These tables are append-only — rows are never updated
or deleted. They enable tracking of:
- Who changed job status and when (job_audit_logs)
- Who modified billing account settings (billing_audit_logs)

Both tables are tenant-scoped with company_id FK and compound indexes.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    # job_audit_logs — immutable audit trail for job status/field changes
    op.create_table(
        "job_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_by_user_id", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_job_audit_logs_job_id", "job_audit_logs", ["job_id"])
    op.create_index("ix_job_audit_logs_company_id", "job_audit_logs", ["company_id"])
    op.create_index("ix_job_audit_logs_created_at", "job_audit_logs", ["created_at"])

    # billing_audit_logs — immutable audit trail for billing account modifications
    op.create_table(
        "billing_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("billing_account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by_user_id", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_billing_audit_logs_company_id", "billing_audit_logs", ["company_id"])
    op.create_index("ix_billing_audit_logs_account_id", "billing_audit_logs", ["billing_account_id"])
    op.create_index("ix_billing_audit_logs_created_at", "billing_audit_logs", ["created_at"])


def downgrade():
    op.drop_index("ix_billing_audit_logs_created_at", table_name="billing_audit_logs")
    op.drop_index("ix_billing_audit_logs_account_id", table_name="billing_audit_logs")
    op.drop_index("ix_billing_audit_logs_company_id", table_name="billing_audit_logs")
    op.drop_table("billing_audit_logs")

    op.drop_index("ix_job_audit_logs_created_at", table_name="job_audit_logs")
    op.drop_index("ix_job_audit_logs_company_id", table_name="job_audit_logs")
    op.drop_index("ix_job_audit_logs_job_id", table_name="job_audit_logs")
    op.drop_table("job_audit_logs")
