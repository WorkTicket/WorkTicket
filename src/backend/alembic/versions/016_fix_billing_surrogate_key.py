"""Add surrogate key to billing_accounts, non-nullable company_id, usage_ledger index

Revision ID: 016_fix_billing_surrogate_key
Revises: 015_fix_push_token_company_id_fk
Create Date: 2026-05-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "016_fix_billing_surrogate_key"
down_revision: str | None = "015_fix_push_token_company_id_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add surrogate key id to billing_accounts
    op.add_column("billing_accounts", sa.Column("id", UUID(as_uuid=True), nullable=True))
    op.alter_column("billing_accounts", "company_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.create_unique_constraint("uq_billing_accounts_company", "billing_accounts", ["company_id"])

    # Make StripeWebhookEvent.company_id non-nullable
    op.alter_column("stripe_webhook_events", "company_id", existing_type=UUID(as_uuid=True), nullable=False)

    # Add composite index on usage_ledger
    op.create_index("ix_usage_ledger_company_created", "usage_ledger", ["company_id", "created_at"])

    # Make Invoice.customer_id nullable
    op.alter_column("invoices", "customer_id", existing_type=UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.drop_column("billing_accounts", "id")
    op.alter_column("billing_accounts", "company_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.drop_constraint("uq_billing_accounts_company", "billing_accounts")
    op.alter_column("stripe_webhook_events", "company_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.drop_index("ix_usage_ledger_company_created", "usage_ledger")
    op.alter_column("invoices", "customer_id", existing_type=UUID(as_uuid=True), nullable=False)
