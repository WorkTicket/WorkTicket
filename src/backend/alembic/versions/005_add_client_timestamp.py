"""add client_timestamp to analytics_events

Revision ID: 005
Revises: 004
Create Date: 2026-05-21 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analytics_events", sa.Column("client_timestamp", sa.DateTime(), nullable=True))
    op.create_index("ix_analytics_events_client_timestamp", "analytics_events", ["client_timestamp"])


def downgrade() -> None:
    op.drop_index("ix_analytics_events_client_timestamp")
    op.drop_column("analytics_events", "client_timestamp")
