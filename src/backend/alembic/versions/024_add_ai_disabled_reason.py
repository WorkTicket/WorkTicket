"""Add ai_disabled_reason column to billing_accounts (H-8)

Revision ID: 024
Revises: 023_add_usage_ledger_partitioning
Create Date: 2026-06-01

"""

import sqlalchemy as sa

from alembic import op

revision = "024"
down_revision = "023_add_usage_ledger_partitioning"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "billing_accounts",
        sa.Column("ai_disabled_reason", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("billing_accounts", "ai_disabled_reason")
