"""add estimate audit snapshots table

Revision ID: 014
Revises: 013
Create Date: 2026-05-23 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "estimate_audit_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("estimates.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB, nullable=False),
        sa.Column("previous_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("diff_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_estimate_audit_estimate_id", "estimate_audit_snapshots", ["estimate_id"])
    op.create_index("ix_estimate_audit_company_id", "estimate_audit_snapshots", ["company_id"])
    op.create_index("ix_estimate_audit_event_type", "estimate_audit_snapshots", ["event_type"])
    op.create_index("ix_estimate_audit_created_at", "estimate_audit_snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_estimate_audit_created_at", table_name="estimate_audit_snapshots")
    op.drop_index("ix_estimate_audit_event_type", table_name="estimate_audit_snapshots")
    op.drop_index("ix_estimate_audit_company_id", table_name="estimate_audit_snapshots")
    op.drop_index("ix_estimate_audit_estimate_id", table_name="estimate_audit_snapshots")
    op.drop_table("estimate_audit_snapshots")
