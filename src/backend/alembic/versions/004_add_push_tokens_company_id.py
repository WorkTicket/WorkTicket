"""add company_id and index to push_tokens

Revision ID: 004
Revises: 003
Create Date: 2026-05-21 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("push_tokens", sa.Column("company_id", sa.String(255), nullable=False, server_default=""))
    op.alter_column("push_tokens", "company_id", server_default=None)
    op.execute(
        "UPDATE push_tokens SET company_id = (SELECT company_id FROM users WHERE users.id = push_tokens.user_id)"
    )
    op.add_column("push_tokens", sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")))
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"])
    op.create_index("ix_push_tokens_company_id", "push_tokens", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_push_tokens_company_id")
    op.drop_index("ix_push_tokens_user_id")
    op.drop_column("push_tokens", "created_at")
    op.drop_column("push_tokens", "company_id")
