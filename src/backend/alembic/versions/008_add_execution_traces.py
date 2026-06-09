"""Add execution_traces table for end-to-end workflow tracing

Revision ID: 008
Revises: 007
Create Date: 2026-05-22

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade():
    op.create_table(
        "execution_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_execution_traces_trace_id", "execution_traces", ["trace_id"])
    op.create_index("ix_execution_traces_job_id", "execution_traces", ["job_id"])
    op.create_index("ix_execution_traces_step_name", "execution_traces", ["step_name"])
    op.create_index("ix_execution_traces_started_at", "execution_traces", ["started_at"])


def downgrade():
    op.drop_table("execution_traces")
