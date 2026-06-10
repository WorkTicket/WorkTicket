"""Add unique constraint on AIJobEstimate and composite index on UsageLedger

Revision ID: 026
Revises: 025
Create Date: 2026-06-02

Adds:
- Unique constraint uq_ai_job_estimate_company_job on ai_job_estimates(company_id, job_id)
- job_id column to ai_job_estimates (if not already present)
- Composite index ix_usage_ledger_company_created on usage_ledger(company_id, created_at)
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    # Add job_id column to ai_job_estimates if it doesn't exist
    conn = op.get_bind()
    result = conn.execute(
        sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='ai_job_estimates' AND column_name='job_id'
    """)
    )
    if result.fetchone() is None:
        op.add_column("ai_job_estimates", sa.Column("job_id", UUID(as_uuid=True), nullable=True))

    # Add unique constraint on AIJobEstimate
    op.create_unique_constraint(
        "uq_ai_job_estimate_company_job",
        "ai_job_estimates",
        ["company_id", "job_id"],
    )

    # Add composite index on UsageLedger (may already exist from 023)
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_usage_ledger_company_created ON usage_ledger (company_id, created_at)")
    )


def downgrade():
    op.drop_constraint("uq_ai_job_estimate_company_job", "ai_job_estimates", type_="unique")
    op.drop_index("ix_usage_ledger_company_created", table_name="usage_ledger")
