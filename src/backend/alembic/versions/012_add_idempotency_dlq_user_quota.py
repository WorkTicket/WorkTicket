"""add idempotency keys, dead letter jobs, user daily usage tables

Revision ID: 012
Revises: 011
Create Date: 2026-05-22 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_json", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_user_idempotency_key"),
    )
    op.create_index("ix_idempotency_keys_user_key", "idempotency_keys", ["user_id", "idempotency_key"])
    op.create_index("ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"])

    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("failure_category", sa.String(50), nullable=True),
        sa.Column("last_state", sa.String(20), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("trace_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dead_letter_jobs_job_id", "dead_letter_jobs", ["job_id"])
    op.create_index("ix_dead_letter_jobs_company_id", "dead_letter_jobs", ["company_id"])
    op.create_index("ix_dead_letter_jobs_created_at", "dead_letter_jobs", ["created_at"])

    op.create_table(
        "user_daily_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("acu_used", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0.0")),
        sa.Column("job_count", sa.Numeric(12, 0), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("user_id", "company_id", "date", name="uq_user_daily_usage"),
    )
    op.create_index("ix_user_daily_usage_user_date", "user_daily_usage", ["user_id", "date"])
    op.create_index("ix_user_daily_usage_company_id", "user_daily_usage", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_user_daily_usage_company_id", table_name="user_daily_usage")
    op.drop_index("ix_user_daily_usage_user_date", table_name="user_daily_usage")
    op.drop_table("user_daily_usage")

    op.drop_index("ix_dead_letter_jobs_created_at", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letter_jobs_company_id", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letter_jobs_job_id", table_name="dead_letter_jobs")
    op.drop_table("dead_letter_jobs")

    op.drop_index("ix_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_user_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
