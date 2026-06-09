"""Add company_id to idempotency_keys for tenant isolation.

Revision ID: 029
Revises: 028
Create Date: 2026-06-05

Adds company_id column to idempotency_keys table and replaces the
single-column unique constraint with a compound (company_id, user_id,
idempotency_key) constraint. This ensures idempotency keys are properly
scoped to the tenant, preventing cross-tenant idempotency key collisions
and enforcing tenant isolation at the database level.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    _conn = op.get_bind()

    op.add_column(
        "idempotency_keys",
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_idempotency_keys_company_id",
        "idempotency_keys",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("uq_user_idempotency_key", "idempotency_keys", type_="unique")

    op.create_unique_constraint(
        "uq_company_user_idempotency_key",
        "idempotency_keys",
        ["company_id", "user_id", "idempotency_key"],
    )

    op.alter_column("idempotency_keys", "company_id", nullable=False)

    op.create_index(
        "ix_idempotency_keys_company_user",
        "idempotency_keys",
        ["company_id", "user_id"],
    )


def downgrade():
    op.drop_index("ix_idempotency_keys_company_user", table_name="idempotency_keys")

    op.drop_constraint("fk_idempotency_keys_company_id", "idempotency_keys", type_="foreignkey")

    op.alter_column("idempotency_keys", "company_id", nullable=True)

    op.drop_constraint("uq_company_user_idempotency_key", "idempotency_keys", type_="unique")

    op.create_unique_constraint(
        "uq_user_idempotency_key",
        "idempotency_keys",
        ["user_id", "idempotency_key"],
    )

    op.drop_column("idempotency_keys", "company_id")
