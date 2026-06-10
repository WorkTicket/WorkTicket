"""Drop duplicate usage_ledger index, add invoice/billing/company indexes, backfill NULLs

Revision ID: 021_fix_indexes_and_nulls
Revises: 020_add_usage_ledger_unique_soft_delete_indexes
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "021_fix_indexes_and_nulls"
down_revision: str | None = "020_add_usage_ledger_unique_soft_delete_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # M1: Drop duplicate index created in migration 010 (ix_usage_ledger_company_id_created)
    # Keep ix_usage_ledger_company_created from migration 016
    op.execute("DROP INDEX IF EXISTS ix_usage_ledger_company_id_created")

    # Create invoices table (model exists but no migration created it)
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("line_items", postgresql.JSONB(), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), default=0.0),
        sa.Column("tax", sa.Numeric(12, 2), default=0.0),
        sa.Column("total", sa.Numeric(12, 2), default=0.0),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_is_deleted_deleted_at", "invoices", ["is_deleted", "deleted_at"])

    # H6: Add indexes to invoices table
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_created_at", "invoices", ["created_at"])
    op.create_index("ix_invoices_company_status", "invoices", ["company_id", "status"])

    # H7: Add indexes on stripe fields
    op.create_index("ix_billing_accounts_stripe_subscription_id", "billing_accounts", ["stripe_subscription_id"])
    op.create_index("ix_companies_stripe_customer_id", "companies", ["stripe_customer_id"])
    op.create_index("ix_companies_stripe_subscription_id", "companies", ["stripe_subscription_id"])

    # M5: Add temp_quota_multiplier column, backfill NULLs, and make non-nullable
    op.add_column("billing_accounts", sa.Column("temp_quota_multiplier", sa.Numeric(4, 2), nullable=True))
    op.execute("UPDATE billing_accounts SET temp_quota_multiplier = 1.00 WHERE temp_quota_multiplier IS NULL")
    op.alter_column("billing_accounts", "temp_quota_multiplier", existing_type=sa.Numeric(4, 2), nullable=False)


def downgrade() -> None:
    op.drop_index("ix_invoices_is_deleted_deleted_at", "invoices")
    op.drop_index("ix_companies_stripe_subscription_id", "companies")
    op.drop_index("ix_companies_stripe_customer_id", "companies")
    op.drop_index("ix_billing_accounts_stripe_subscription_id", "billing_accounts")
    op.drop_index("ix_invoices_company_status", "invoices")
    op.drop_index("ix_invoices_created_at", "invoices")
    op.drop_index("ix_invoices_status", "invoices")
    op.drop_index("ix_invoices_company_id", "invoices")
    op.drop_table("invoices")
    op.create_index("ix_usage_ledger_company_id_created", "usage_ledger", ["company_id", "created_at"])
    op.drop_column("billing_accounts", "temp_quota_multiplier")
