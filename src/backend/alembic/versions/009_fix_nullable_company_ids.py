"""fix nullable company_id on ai_audit_logs and execution_traces

Revision ID: 009
Revises: 008
Create Date: 2026-05-22 00:00:00.000000
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove any rows with NULL company_id before adding NOT NULL constraint
    op.execute("DELETE FROM ai_audit_logs WHERE company_id IS NULL")
    op.execute("DELETE FROM execution_traces WHERE company_id IS NULL")
    # Make company_id NOT NULL on ai_audit_logs
    op.alter_column("ai_audit_logs", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    # Make company_id NOT NULL on execution_traces
    op.alter_column("execution_traces", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    # Add index on execution_traces.company_id for tenant-scoped queries
    op.create_index("ix_execution_traces_company_id", "execution_traces", ["company_id"])
    # Index ix_ai_audit_logs_company_id already created in migration 002


def downgrade() -> None:
    op.drop_index("ix_execution_traces_company_id", table_name="execution_traces")
    op.alter_column("execution_traces", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("ai_audit_logs", "company_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
