"""Add ON DELETE CASCADE/SET NULL to all foreign keys

Revision ID: 022_add_ondelete_cascade
Revises: 021_fix_indexes_and_nulls
Create Date: 2026-05-31 00:00:00.000000

Adds ondelete behavior to all foreign keys that lack it:
- CASCADE for child tables that should die with parent
- SET NULL for audit/analytics tables that should preserve records
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022_add_ondelete_cascade"
down_revision: str | None = "021_fix_indexes_and_nulls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Map of (table, fk_name, column) -> (ref_table, ondelete_action)
_FK_UPDATES = [
    # --- UsageLedger ---
    ("usage_ledger", "usage_ledger_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- BillingAccount ---
    ("billing_accounts", "billing_accounts_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- AIJobEstimate ---
    ("ai_job_estimates", "ai_job_estimates_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- StripeWebhookEvent (SET NULL to preserve dedup entries) ---
    ("stripe_webhook_events", "stripe_webhook_events_company_id_fkey", "company_id", "companies.id", "SET NULL"),
    # --- Invoice ---
    ("invoices", "invoices_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    ("invoices", "invoices_job_id_fkey", "job_id", "jobs.id", "SET NULL"),
    ("invoices", "invoices_customer_id_fkey", "customer_id", "customers.id", "SET NULL"),
    # --- Job ---
    ("jobs", "jobs_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    ("jobs", "jobs_customer_id_fkey", "customer_id", "customers.id", "SET NULL"),
    ("jobs", "jobs_technician_id_fkey", "technician_id", "users.id", "SET NULL"),
    # --- JobMedia ---
    ("job_media", "job_media_job_id_fkey", "job_id", "jobs.id", "CASCADE"),
    ("job_media", "job_media_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- AIOutput ---
    ("ai_outputs", "ai_outputs_job_id_fkey", "job_id", "jobs.id", "CASCADE"),
    ("ai_outputs", "ai_outputs_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- Quote ---
    ("quotes", "quotes_job_id_fkey", "job_id", "jobs.id", "CASCADE"),
    ("quotes", "quotes_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- User ---
    ("users", "users_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- Customer ---
    ("customers", "customers_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- PushToken ---
    ("push_tokens", "push_tokens_user_id_fkey", "user_id", "users.id", "CASCADE"),
    ("push_tokens", "push_tokens_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    # --- Estimates ---
    ("estimates", "estimates_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    ("estimate_line_items", "estimate_line_items_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    ("estimate_line_items", "estimate_line_items_estimate_id_fkey", "estimate_id", "estimates.id", "CASCADE"),
    ("estimate_snapshots", "estimate_snapshots_company_id_fkey", "company_id", "companies.id", "CASCADE"),
    ("estimate_snapshots", "estimate_snapshots_job_id_fkey", "job_id", "jobs.id", "SET NULL"),
    ("estimate_snapshots", "estimate_snapshots_estimate_id_fkey", "estimate_id", "estimates.id", "SET NULL"),
    # --- EstimateAuditSnapshot ---
    ("estimate_audit_snapshots", "estimate_audit_snapshots_estimate_id_fkey", "estimate_id", "estimates.id", "CASCADE"),
    ("estimate_audit_snapshots", "estimate_audit_snapshots_company_id_fkey", "company_id", "companies.id", "CASCADE"),
]


def _fk_exists(table: str, fk_name: str) -> bool:
    """Check if a foreign key constraint exists before dropping."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name AND conrelid = :table::regclass"),
        {"name": fk_name, "table": table},
    )
    return result.scalar() is not None


def upgrade() -> None:
    for table, fk_name, column, ref, action in _FK_UPDATES:
        if _fk_exists(table, fk_name):
            op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            ref.split(".")[0],
            [column],
            [ref.split(".")[1]],
            ondelete=action,
        )

    # Also add FK constraints to analytics/audit/traces tables (MEDIUM-7)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'analytics_events_company_id_fkey'
            ) THEN
                ALTER TABLE analytics_events
                    ADD CONSTRAINT analytics_events_company_id_fkey
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ai_audit_logs_company_id_fkey'
            ) THEN
                ALTER TABLE ai_audit_logs
                    ADD CONSTRAINT ai_audit_logs_company_id_fkey
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'execution_traces_company_id_fkey'
            ) THEN
                ALTER TABLE execution_traces
                    ADD CONSTRAINT execution_traces_company_id_fkey
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    for table, fk_name, column, ref, _action in _FK_UPDATES:
        if _fk_exists(table, fk_name):
            op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(fk_name, table, ref.split(".")[0], [column], [ref.split(".")[1]])

    op.execute("ALTER TABLE analytics_events DROP CONSTRAINT IF EXISTS analytics_events_company_id_fkey")
    op.execute("ALTER TABLE ai_audit_logs DROP CONSTRAINT IF EXISTS ai_audit_logs_company_id_fkey")
    op.execute("ALTER TABLE execution_traces DROP CONSTRAINT IF EXISTS execution_traces_company_id_fkey")
