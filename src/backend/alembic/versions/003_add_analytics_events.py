"""add analytics_events table

Revision ID: 003
Revises: 002
Create Date: 2026-05-21 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )

    op.create_index("ix_analytics_events_event_name", "analytics_events", ["event_name"])
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_events_company_id", "analytics_events", ["company_id"])
    op.create_index("ix_analytics_events_timestamp", "analytics_events", ["timestamp"])
    op.create_index("ix_analytics_events_job_id", "analytics_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_analytics_events_job_id")
    op.drop_index("ix_analytics_events_timestamp")
    op.drop_index("ix_analytics_events_company_id")
    op.drop_index("ix_analytics_events_user_id")
    op.drop_index("ix_analytics_events_event_name")
    op.drop_table("analytics_events")
