"""Add composite index for WebSocket polling on ai_outputs

Revision ID: 019_add_ai_output_company_job_created_index
Revises: 018_add_soft_delete_to_jobs
Create Date: 2026-05-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_add_ai_output_company_job_created_index"
down_revision: str | None = "018_add_soft_delete_to_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ai_outputs_company_job_created",
        "ai_outputs",
        ["company_id", "job_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_outputs_company_job_created")
