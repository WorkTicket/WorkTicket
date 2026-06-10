"""Add composite indexes on tenant-scoped tables for multi-tenant query performance.

Revision ID: 037
Revises: 036
Create Date: 2026-06-06

Fixes identified in DDA v1.0 (Scalability section):
Several high-traffic tables lack composite (company_id, ...) indexes
that are essential for multi-tenant query performance at scale.
"""

import sqlalchemy as sa

from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name},
    )
    return result.scalar() is not None


def upgrade():
    # Add missing is_deleted column to users (soft-delete support)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'is_deleted'"
        )
    )
    if result.scalar() is None:
        op.add_column("users", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    if not _index_exists("ix_customers_company_email"):
        op.create_index("ix_customers_company_email", "customers", ["company_id", "email"])
    if not _index_exists("ix_customers_company_name"):
        op.create_index("ix_customers_company_name", "customers", ["company_id", "name"])
    if not _index_exists("ix_job_media_company_job"):
        op.create_index("ix_job_media_company_job", "job_media", ["company_id", "job_id"])
    if not _index_exists("ix_jobs_company_status"):
        op.create_index(
            "ix_jobs_company_status", "jobs", ["company_id", "status"], postgresql_where=sa.text("is_deleted = false")
        )
    if not _index_exists("ix_quotes_company_status"):
        op.create_index(
            "ix_quotes_company_status", "quotes", ["company_id", "status"], postgresql_where=sa.text("is_deleted = false")
        )
    if not _index_exists("ix_users_company_email"):
        op.create_index("ix_users_company_email", "users", ["company_id", "email"])
    if not _index_exists("ix_users_company_role"):
        op.create_index("ix_users_company_role", "users", ["company_id", "role"])
    if not _index_exists("ix_users_company_is_deleted"):
        op.create_index("ix_users_company_is_deleted", "users", ["company_id", "is_deleted"])
    if not _index_exists("ix_services_company_id"):
        op.create_index("ix_services_company_id", "services", ["company_id", "id"])
    if not _index_exists("ix_estimates_company_status"):
        op.create_index(
            "ix_estimates_company_status",
            "estimates",
            ["company_id", "status"],
            postgresql_where=sa.text("is_deleted = false"),
        )
    if not _index_exists("ix_push_tokens_company_user"):
        op.create_index("ix_push_tokens_company_user", "push_tokens", ["company_id", "user_id"])


def downgrade():
    if _index_exists("ix_push_tokens_company_user"):
        op.drop_index("ix_push_tokens_company_user", table_name="push_tokens")
    if _index_exists("ix_estimates_company_status"):
        op.drop_index("ix_estimates_company_status", table_name="estimates")
    if _index_exists("ix_services_company_id"):
        op.drop_index("ix_services_company_id", table_name="services")
    if _index_exists("ix_users_company_is_deleted"):
        op.drop_index("ix_users_company_is_deleted", table_name="users")
    if _index_exists("ix_users_company_role"):
        op.drop_index("ix_users_company_role", table_name="users")
    if _index_exists("ix_users_company_email"):
        op.drop_index("ix_users_company_email", table_name="users")
    if _index_exists("ix_quotes_company_status"):
        op.drop_index("ix_quotes_company_status", table_name="quotes")
    if _index_exists("ix_jobs_company_status"):
        op.drop_index("ix_jobs_company_status", table_name="jobs")
    if _index_exists("ix_job_media_company_job"):
        op.drop_index("ix_job_media_company_job", table_name="job_media")
    if _index_exists("ix_customers_company_name"):
        op.drop_index("ix_customers_company_name", table_name="customers")
    if _index_exists("ix_customers_company_email"):
        op.drop_index("ix_customers_company_email", table_name="customers")
