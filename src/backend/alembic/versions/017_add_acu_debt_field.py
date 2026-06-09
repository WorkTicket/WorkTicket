"""Add acu_debt field to BillingAccount for tracking reconciliation errors

Revision ID: 017_add_acu_debt_field
Revises: 016_fix_billing_surrogate_key
Create Date: 2026-05-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017_add_acu_debt_field"
down_revision: str | None = "016_fix_billing_surrogate_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add acu_debt column to billing_accounts
    op.add_column("billing_accounts", sa.Column("acu_debt", NUMERIC(12, 4), nullable=False, server_default="0"))


def downgrade() -> None:
    # Remove acu_debt column from billing_accounts
    op.drop_column("billing_accounts", "acu_debt")
