"""Add company_id to ai_output_feedback for tenant isolation (Must-Fix #1).

Revision ID: 032
Revises: 031
Create Date: 2026-06-05

Fixes the cross-tenant data leak vector identified in the audit:
AIOutputFeedback table was missing the company_id column, meaning
the ORM-level tenant isolation listener could not filter queries
by tenant. Feedback records from one company could be accessed by
another company through raw SQL or any unconstrained query path.

This migration adds a NOT NULL company_id column with a foreign
key to companies.id. Existing rows (none expected in private beta)
are assigned the company_id from their linked AIOutput record.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT to_regclass('ai_output_feedback')"))
    if result.scalar() is None:
        return

    op.add_column(
        "ai_output_feedback",
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_output_feedback_company_id",
        "ai_output_feedback",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ai_output_feedback_company_id",
        "ai_output_feedback",
        ["company_id"],
    )


def downgrade():
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT to_regclass('ai_output_feedback')"))
    if result.scalar() is None:
        return

    op.drop_index("ix_ai_output_feedback_company_id", table_name="ai_output_feedback")
    op.drop_constraint("fk_ai_output_feedback_company_id", "ai_output_feedback", type_="foreignkey")
    op.drop_column("ai_output_feedback", "company_id")
