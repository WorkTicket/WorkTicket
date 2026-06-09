"""add execution state, heartbeat, billing period, credit columns

Revision ID: 011
Revises: 010
Create Date: 2026-05-22 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("ai_processing_state", sa.String(20), server_default="none", nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("ai_processing_updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_jobs_ai_processing_state", "jobs", ["ai_processing_state"])

    op.add_column(
        "billing_accounts",
        sa.Column("reservation_heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "billing_accounts",
        sa.Column("billing_period_start", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "billing_accounts",
        sa.Column("billing_period_end", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "usage_ledger",
        sa.Column("is_credit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "usage_ledger",
        sa.Column("credit_reason", sa.String(255), nullable=True),
    )
    op.add_column(
        "usage_ledger",
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "usage_ledger",
        sa.Column("billing_period", sa.String(7), nullable=True),
    )
    op.create_index("ix_usage_ledger_is_credit", "usage_ledger", ["is_credit"])

    op.add_column(
        "ai_job_estimates",
        sa.Column("billing_period", sa.String(7), nullable=True),
    )
    op.create_index("ix_ai_job_estimates_billing_period", "ai_job_estimates", ["billing_period"])


def downgrade() -> None:
    op.drop_index("ix_ai_job_estimates_billing_period", table_name="ai_job_estimates")
    op.drop_column("ai_job_estimates", "billing_period")

    op.drop_index("ix_usage_ledger_is_credit", table_name="usage_ledger")
    op.drop_column("usage_ledger", "billing_period")
    op.drop_column("usage_ledger", "original_job_id")
    op.drop_column("usage_ledger", "credit_reason")
    op.drop_column("usage_ledger", "is_credit")

    op.drop_column("billing_accounts", "billing_period_end")
    op.drop_column("billing_accounts", "billing_period_start")
    op.drop_column("billing_accounts", "reservation_heartbeat_at")

    op.drop_index("ix_jobs_ai_processing_state", table_name="jobs")
    op.drop_column("jobs", "ai_processing_updated_at")
    op.drop_column("jobs", "ai_processing_state")
