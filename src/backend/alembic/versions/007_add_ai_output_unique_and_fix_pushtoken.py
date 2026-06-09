"""Add unique constraint to AIOutput, fix PushToken company_id type

Revision ID: 007
Revises: 006_add_missing_indexes
Create Date: 2026-05-22

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007"
down_revision: str | None = "006_add_missing_indexes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade():
    op.create_unique_constraint(
        "uq_ai_output_job_type_company",
        "ai_outputs",
        ["job_id", "output_type", "company_id"],
    )

    op.drop_column("push_tokens", "company_id")
    op.add_column(
        "push_tokens",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
    )

    op.add_column(
        "job_media",
        sa.Column("storage_key", sa.String(1024), nullable=True),
    )


def downgrade():
    op.drop_column("job_media", "storage_key")

    op.drop_column("push_tokens", "company_id")
    op.add_column(
        "push_tokens",
        sa.Column("company_id", sa.String(255), nullable=False),
    )

    op.drop_constraint("uq_ai_output_job_type_company", "ai_outputs", type_="unique")
