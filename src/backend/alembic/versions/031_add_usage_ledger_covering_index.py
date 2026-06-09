"""Add covering index for usage_ledger range queries (S-1 fix).

Revision ID: 031
Revises: 030
Create Date: 2026-06-05

Adds a composite index on usage_ledger (company_id, created_at, job_id)
to cover the most common query pattern: WHERE company_id = ? ORDER BY
created_at DESC. The existing partial unique index only covers (job_id,
company_id) for uniqueness enforcement and does not accelerate range
scans by company_id.

This index also enables index-only scans for the usage history endpoint
since it includes created_at (the ORDER BY column) in the index.
"""

import sqlalchemy as sa

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_usage_ledger_company_created_job",
        "usage_ledger",
        ["company_id", sa.text("created_at DESC"), "job_id"],
    )


def downgrade():
    op.drop_index(
        "ix_usage_ledger_company_created_job",
        table_name="usage_ledger",
    )
