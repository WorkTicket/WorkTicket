"""add missing indexes for hot query paths

Revision ID: 006
Revises: 005
Create Date: 2026-05-21 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006_add_missing_indexes"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_analytics_events_company_event_time", "analytics_events", ["company_id", "event_name", "timestamp"]
    )
    op.create_index("ix_push_tokens_company_user", "push_tokens", ["company_id", "user_id"])
    op.create_index("ix_ai_outputs_job_company_type", "ai_outputs", ["job_id", "company_id", "output_type"])
    op.create_index("ix_quotes_company_status", "quotes", ["company_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_quotes_company_status")
    op.drop_index("ix_ai_outputs_job_company_type")
    op.drop_index("ix_push_tokens_company_user")
    op.drop_index("ix_analytics_events_company_event_time")
