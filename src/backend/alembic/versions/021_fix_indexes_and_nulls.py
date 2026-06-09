"""Drop duplicate usage_ledger index, add invoice/billing/company indexes, backfill NULLs

Revision ID: 021_fix_indexes_and_nulls
Revises: 020_add_usage_ledger_unique_soft_delete_indexes
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "021_fix_indexes_and_nulls"
down_revision: str | None = "020_add_usage_ledger_unique_soft_delete_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # M1: Drop duplicate index created in migration 010 (ix_usage_ledger_company_id_created)
    # Keep ix_usage_ledger_company_created from migration 016
    op.execute("DROP INDEX IF EXISTS ix_usage_ledger_company_id_created")

    # H6: Add indexes to invoices table
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_created_at", "invoices", ["created_at"])
    op.create_index("ix_invoices_company_status", "invoices", ["company_id", "status"])

    # H7: Add indexes on stripe fields
    op.create_index("ix_billing_accounts_stripe_subscription_id", "billing_accounts", ["stripe_subscription_id"])
    op.create_index("ix_companies_stripe_customer_id", "companies", ["stripe_customer_id"])
    op.create_index("ix_companies_stripe_subscription_id", "companies", ["stripe_subscription_id"])

    # M5: Backfill NULL temp_quota_multiplier and make non-nullable
    op.execute("UPDATE billing_accounts SET temp_quota_multiplier = 1.00 WHERE temp_quota_multiplier IS NULL")
    op.alter_column("billing_accounts", "temp_quota_multiplier", existing_type=sa.Numeric(4, 2), nullable=False)


def downgrade() -> None:
    op.drop_index("ix_companies_stripe_subscription_id", "companies")
    op.drop_index("ix_companies_stripe_customer_id", "companies")
    op.drop_index("ix_billing_accounts_stripe_subscription_id", "billing_accounts")
    op.drop_index("ix_invoices_company_status", "invoices")
    op.drop_index("ix_invoices_created_at", "invoices")
    op.drop_index("ix_invoices_status", "invoices")
    op.drop_index("ix_invoices_company_id", "invoices")
    op.create_index("ix_usage_ledger_company_id_created", "usage_ledger", ["company_id", "created_at"])
    op.alter_column("billing_accounts", "temp_quota_multiplier", existing_type=sa.Numeric(4, 2), nullable=True)
