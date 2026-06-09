"""fix push token company_id foreign key with safety checks

Revision ID: 015
Revises: 014
Create Date: 2026-05-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Remove any rows where company_id is NULL
    conn.execute(sa.text("DELETE FROM push_tokens WHERE company_id IS NULL"))

    # Step 2: Remove rows where company_id is not a valid UUID
    conn.execute(
        sa.text(
            "DELETE FROM push_tokens WHERE company_id !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'"
        )
    )

    # Step 3: Remove orphaned push tokens referencing non-existent companies
    conn.execute(
        sa.text("""
        DELETE FROM push_tokens
        WHERE company_id NOT IN (SELECT id::text FROM companies)
    """)
    )

    # Step 4: Add supporting index on company_id for FK performance
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_push_tokens_company_id ON push_tokens (company_id)"))

    # Step 5: Alter column type from String to UUID and add foreign key constraint
    op.alter_column(
        "push_tokens",
        "company_id",
        existing_type=sa.String(255),
        type_=postgresql.UUID(as_uuid=True),
        postgresql_using="company_id::uuid",
        nullable=False,
    )

    # Step 6: Add foreign key constraint with CASCADE delete
    op.create_foreign_key(
        "fk_push_tokens_company_id", "push_tokens", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_push_tokens_company_id", "push_tokens", type_="foreignkey")

    op.alter_column(
        "push_tokens",
        "company_id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(255),
        existing_nullable=False,
    )

    op.execute(sa.text("DROP INDEX IF EXISTS ix_push_tokens_company_id"))
