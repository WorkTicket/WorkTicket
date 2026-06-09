"""Add PII encrypted fields and PII access audit log table.

Revision ID: 028
Revises: 027
Create Date: 2026-06-05

Adds encrypted columns for PII fields on User and Customer tables
as a dual-write strategy. Plaintext fields remain for backward compatibility
during the rollout period.

Also creates the pii_access_audit table for compliance logging.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade():
    _conn = op.get_bind()

    # Add encrypted email column to users (nullable during backfill)
    op.add_column("users", sa.Column("email_encrypted", sa.Text(), nullable=True))

    # Add encrypted name and address columns to customers
    op.add_column("customers", sa.Column("name_encrypted", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("address_encrypted", sa.Text(), nullable=True))

    # Create PII access audit log table
    op.create_table(
        "pii_access_audit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("access_reason", sa.String(100), nullable=False, server_default="read"),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Backfill encrypted email from plaintext email (will be a no-op if PII_ENCRYPTION_KEY not set)
    # In production, run a separate backfill script with the key available


def downgrade():
    op.drop_table("pii_access_audit")
    op.drop_column("customers", "address_encrypted")
    op.drop_column("customers", "name_encrypted")
    op.drop_column("users", "email_encrypted")
