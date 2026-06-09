"""Add PII encrypted field columns for column-level encryption.

Revision ID: 035
Revises: 034
Create Date: 2026-06-05

Adds encrypted_ fields alongside existing PII columns (email, name)
to support gradual migration to column-level encryption. The new columns
store AES-256-GCM encrypted JSON blobs. Application code reads from
encrypted_ fields when available, falling back to plaintext columns.
"""

import sqlalchemy as sa

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("encrypted_email", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("encrypted_name", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("encrypted_email", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("encrypted_phone", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("encrypted_name", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("customers", "encrypted_name")
    op.drop_column("customers", "encrypted_phone")
    op.drop_column("customers", "encrypted_email")
    op.drop_column("users", "encrypted_name")
    op.drop_column("users", "encrypted_email")
