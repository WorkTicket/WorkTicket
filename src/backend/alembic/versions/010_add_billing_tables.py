"""add billing_accounts, usage_ledger, ai_job_estimates tables

Revision ID: 010
Revises: 009
Create Date: 2026-05-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_accounts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("plan", sa.String(50), server_default="free", nullable=False),
        sa.Column("monthly_quota_acu", sa.Numeric(12, 4), server_default=sa.text("15.0"), nullable=False),
        sa.Column("used_acu", sa.Numeric(12, 4), server_default=sa.text("0.0"), nullable=False),
        sa.Column("reserved_acu", sa.Numeric(12, 4), server_default=sa.text("0.0"), nullable=False),
        sa.Column("overage_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ai_disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("risk_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("reset_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_accounts_company_id", "billing_accounts", ["company_id"])
    op.create_index("ix_billing_accounts_plan", "billing_accounts", ["plan"])
    op.create_index("ix_billing_accounts_ai_disabled", "billing_accounts", ["ai_disabled"])

    op.create_table(
        "usage_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("text_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("vision_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("audio_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_ledger_company_id", "usage_ledger", ["company_id"])
    op.create_index("ix_usage_ledger_company_id_created", "usage_ledger", ["company_id", "created_at"])
    op.create_index("ix_usage_ledger_job_id", "usage_ledger", ["job_id"])

    op.create_table(
        "ai_job_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("estimated_text_cost", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("estimated_vision_cost", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("estimated_audio_cost", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("estimated_total_cost", sa.Numeric(12, 6), server_default=sa.text("0.0"), nullable=False),
        sa.Column("approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rejected_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_job_estimates_company_id", "ai_job_estimates", ["company_id"])
    op.create_index("ix_ai_job_estimates_job_id", "ai_job_estimates", ["job_id"])


def downgrade() -> None:
    op.drop_table("ai_job_estimates")
    op.drop_table("usage_ledger")
    op.drop_table("billing_accounts")
