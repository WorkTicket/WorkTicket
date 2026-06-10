"""DEP-1: Pre-migration checks for irreversible migrations

Revision ID: 025
Revises: 024_add_ai_disabled_reason
Create Date: 2026-06-01

This migration checks for duplicates BEFORE applying unique constraints.
"""

from sqlalchemy import text

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def check_for_usage_ledger_duplicates(connection):
    """Check for duplicate (job_id, company_id) pairs in usage_ledger before adding unique constraint."""
    result = connection.execute(
        text("""
        SELECT job_id, company_id, COUNT(*)
        FROM usage_ledger
        WHERE job_id IS NOT NULL
        GROUP BY job_id, company_id
        HAVING COUNT(*) > 1
    """)
    )
    duplicates = result.fetchall()
    if duplicates:
        raise Exception(
            f"Cannot apply unique constraint on usage_ledger(job_id, company_id) — "
            f"found {len(duplicates)} duplicate pairs. "
            f"Run the dedup script before applying this migration. "
            f"First duplicate: job_id={duplicates[0][0]}, company_id={duplicates[0][1]}, count={duplicates[0][2]}"
        )


def upgrade():
    connection = op.get_bind()
    check_for_usage_ledger_duplicates(connection)
    # The unique index was already added in migration 020;
    # this check ensures future migrations don't run on dirty data.


def downgrade():
    pass
