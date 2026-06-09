"""Add storage quota tracking to billing accounts.

Revision ID: 034
Revises: 033
Create Date: 2026-06-05

Adds per-tenant storage quota columns to prevent unbounded storage
growth. Default quota is 5GB (5 * 1024^3 bytes). Used bytes are
tracked incrementally on upload and decremented on deletion.
"""

import sqlalchemy as sa

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "billing_accounts",
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("5368709120")),
    )
    op.add_column(
        "billing_accounts",
        sa.Column("used_storage_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )


def downgrade():
    op.drop_column("billing_accounts", "used_storage_bytes")
    op.drop_column("billing_accounts", "storage_quota_bytes")
