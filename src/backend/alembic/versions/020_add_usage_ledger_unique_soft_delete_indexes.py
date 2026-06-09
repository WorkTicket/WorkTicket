"""Add unique index on usage_ledger(job_id, company_id) and soft-delete composite indexes

Revision ID: 020_add_usage_ledger_unique_soft_delete_indexes
Revises: 019_add_ai_output_company_job_created_index
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "020_add_usage_ledger_unique_soft_delete_indexes"
down_revision: str | None = "019_add_ai_output_company_job_created_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Partial unique index on usage_ledger(job_id, company_id) for non-null job_ids.
    # Prevents duplicate UsageLedger entries for the same job (C2 fix).
    # Using a partial index avoids issues with PostgreSQL treating multiple
    # NULL job_id values as distinct (which is the default UNIQUE behavior).
    op.execute("DELETE FROM usage_ledger WHERE job_id IS NULL")
    op.create_index(
        "ix_usage_ledger_job_company_unique",
        "usage_ledger",
        ["job_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )

    # Composite indexes for soft-delete purge queries (M8 fix)
    op.create_index(
        "ix_jobs_is_deleted_deleted_at",
        "jobs",
        ["is_deleted", "deleted_at"],
    )
    op.create_index(
        "ix_quotes_is_deleted_deleted_at",
        "quotes",
        ["is_deleted", "deleted_at"],
    )
    op.create_index(
        "ix_estimates_is_deleted_deleted_at",
        "estimates",
        ["is_deleted", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_ledger_job_company_unique")
    op.drop_index("ix_jobs_is_deleted_deleted_at")
    op.drop_index("ix_quotes_is_deleted_deleted_at")
    op.drop_index("ix_estimates_is_deleted_deleted_at")
