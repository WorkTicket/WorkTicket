"""add database indexes

Revision ID: 002
Revises: 001
Create Date: 2026-05-21 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_jobs_company_id_status", "jobs", ["company_id", "status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_job_media_job_id", "job_media", ["job_id"])
    op.create_index("ix_job_media_company_id", "job_media", ["company_id"])
    op.create_index("ix_ai_outputs_job_id", "ai_outputs", ["job_id"])
    op.create_index("ix_ai_outputs_company_id", "ai_outputs", ["company_id"])
    op.create_index("ix_quotes_company_id", "quotes", ["company_id"])
    op.create_index("ix_quotes_job_id", "quotes", ["job_id"])
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index("ix_ai_audit_logs_created_at", "ai_audit_logs", ["created_at"])
    op.create_index("ix_ai_audit_logs_company_id", "ai_audit_logs", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_audit_logs_company_id")
    op.drop_index("ix_ai_audit_logs_created_at")
    op.drop_index("ix_customers_company_id")
    op.drop_index("ix_users_company_id")
    op.drop_index("ix_quotes_job_id")
    op.drop_index("ix_quotes_company_id")
    op.drop_index("ix_ai_outputs_company_id")
    op.drop_index("ix_ai_outputs_job_id")
    op.drop_index("ix_job_media_company_id")
    op.drop_index("ix_job_media_job_id")
    op.drop_index("ix_jobs_created_at")
    op.drop_index("ix_jobs_company_id_status")
