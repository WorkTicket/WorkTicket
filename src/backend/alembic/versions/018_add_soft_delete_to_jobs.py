"""Add soft-delete columns (is_deleted, deleted_at) to jobs table

Revision ID: 018_add_soft_delete_to_jobs
Revises: 017_add_acu_debt_field
Create Date: 2026-05-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018_add_soft_delete_to_jobs"
down_revision: str | None = "017_add_acu_debt_field"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("jobs", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "deleted_at")
    op.drop_column("jobs", "is_deleted")
