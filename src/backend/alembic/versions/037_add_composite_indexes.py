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


def upgrade():
    op.create_index("ix_customers_company_email", "customers", ["company_id", "email"])
    op.create_index("ix_customers_company_name", "customers", ["company_id", "name"])
    op.create_index("ix_job_media_company_job", "job_media", ["company_id", "job_id"])
    op.create_index(
        "ix_jobs_company_status", "jobs", ["company_id", "status"], postgresql_where=sa.text("is_deleted = false")
    )
    op.create_index(
        "ix_quotes_company_status", "quotes", ["company_id", "status"], postgresql_where=sa.text("is_deleted = false")
    )
    op.create_index("ix_users_company_email", "users", ["company_id", "email"])
    op.create_index("ix_users_company_role", "users", ["company_id", "role"])
    op.create_index("ix_users_company_is_deleted", "users", ["company_id", "is_deleted"])
    op.create_index("ix_services_company_id", "services", ["company_id", "id"])
    op.create_index(
        "ix_estimates_company_status",
        "estimates",
        ["company_id", "status"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("ix_push_tokens_company_user", "push_tokens", ["company_id", "user_id"])


def downgrade():
    op.drop_index("ix_push_tokens_company_user", table_name="push_tokens")
    op.drop_index("ix_estimates_company_status", table_name="estimates", postgresql_where=sa.text("is_deleted = false"))
    op.drop_index("ix_services_company_id", table_name="services")
    op.drop_index("ix_users_company_is_deleted", table_name="users")
    op.drop_index("ix_users_company_role", table_name="users")
    op.drop_index("ix_users_company_email", table_name="users")
    op.drop_index("ix_quotes_company_status", table_name="quotes", postgresql_where=sa.text("is_deleted = false"))
    op.drop_index("ix_jobs_company_status", table_name="jobs", postgresql_where=sa.text("is_deleted = false"))
    op.drop_index("ix_job_media_company_job", table_name="job_media")
    op.drop_index("ix_customers_company_name", table_name="customers")
    op.drop_index("ix_customers_company_email", table_name="customers")
