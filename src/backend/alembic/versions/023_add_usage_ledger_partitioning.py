"""Monthly partitioning for usage_ledger table.

UsageLedger has grown to ~10M rows. Monthly range partitioning on created_at
improves query performance for billing-period scans and enables efficient
DROP-partition for data retention.

Revision ID: 023_add_usage_ledger_partitioning
Revises: 022_add_ondelete_cascade
Create Date: 2026-01-15 10:00:00.000000
"""

import contextlib

import sqlalchemy as sa

from alembic import op

revision = "023_add_usage_ledger_partitioning"
down_revision = "022_add_ondelete_cascade"
branch_labels = None
depends_on = None


PARTITION_TABLES = [
    "usage_ledger_2025_01",
    "usage_ledger_2025_02",
    "usage_ledger_2025_03",
    "usage_ledger_2025_04",
    "usage_ledger_2025_05",
    "usage_ledger_2025_06",
    "usage_ledger_2025_07",
    "usage_ledger_2025_08",
    "usage_ledger_2025_09",
    "usage_ledger_2025_10",
    "usage_ledger_2025_11",
    "usage_ledger_2025_12",
    "usage_ledger_2026_01",
    "usage_ledger_2026_02",
    "usage_ledger_2026_03",
    "usage_ledger_2026_04",
    "usage_ledger_2026_05",
    "usage_ledger_2026_06",
    "usage_ledger_2026_07",
    "usage_ledger_2026_08",
    "usage_ledger_2026_09",
    "usage_ledger_2026_10",
    "usage_ledger_2026_11",
    "usage_ledger_2026_12",
]


def upgrade():
    conn = op.get_bind()
    # 1. Rename existing table to become the default partition
    op.execute("ALTER TABLE usage_ledger RENAME TO usage_ledger_old")

    # 2. Create partitioned table with same schema
    op.execute("""
        CREATE TABLE usage_ledger (
            id UUID NOT NULL,
            company_id UUID NOT NULL,
            job_id UUID,
            text_units INTEGER DEFAULT 0,
            vision_units INTEGER DEFAULT 0,
            audio_units INTEGER DEFAULT 0,
            cost_usd NUMERIC(12, 6) DEFAULT 0.0,
            estimated_cost_usd NUMERIC(12, 6) DEFAULT 0.0,
            model_used VARCHAR(100),
            execution_time_ms INTEGER,
            is_credit BOOLEAN DEFAULT FALSE,
            credit_reason VARCHAR(255),
            original_job_id UUID,
            user_id VARCHAR(255),
            billing_period VARCHAR(7),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # 3. Create partitions for each month
    for _i, part in enumerate(PARTITION_TABLES):
        parts = part.split("_")
        year = int(parts[2])
        month = int(parts[3])
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        op.execute(f"""
            CREATE TABLE {part} PARTITION OF usage_ledger
            FOR VALUES FROM ('{year:04d}-{month:02d}-01')
            TO ('{next_year:04d}-{next_month:02d}-01')
        """)

    # 4. Carve out a default partition for data outside range
    op.execute("""
        CREATE TABLE usage_ledger_default PARTITION OF usage_ledger
        FOR VALUES FROM (MINVALUE) TO ('2025-01-01')
    """)
    op.execute("""
        CREATE TABLE usage_ledger_future PARTITION OF usage_ledger
        FOR VALUES FROM ('2027-01-01') TO (MAXVALUE)
    """)

    # 5. Drop old table if empty (fresh DB) — avoids index name conflict
    row_count = conn.execute(sa.text("SELECT COUNT(*) FROM usage_ledger_old")).scalar()
    if row_count and row_count > 0:
        with contextlib.suppress(Exception):
            op.drop_index("ix_usage_ledger_company_created", table_name="usage_ledger_old")
        with contextlib.suppress(Exception):
            op.drop_index("ix_usage_ledger_job_company_unique", table_name="usage_ledger_old")
    else:
        op.execute("DROP TABLE usage_ledger_old")

    # 6. Create indexes on partitioned table
    op.create_index("ix_usage_ledger_company_created", "usage_ledger", ["company_id", "created_at"])
    op.create_index("ix_usage_ledger_created_at", "usage_ledger", ["created_at"])
    op.create_index("ix_usage_ledger_billing_period", "usage_ledger", ["billing_period"])

    # 7. Attach old data as a single partition (if there are rows)
    if row_count and row_count > 0:
        op.execute("ALTER TABLE usage_ledger_old ADD COLUMN user_id VARCHAR(255)")
        op.execute("ALTER TABLE usage_ledger_old DROP CONSTRAINT usage_ledger_pkey")
        op.execute("ALTER TABLE usage_ledger_old ADD PRIMARY KEY (id, created_at)")
        op.execute("""
            ALTER TABLE usage_ledger ATTACH PARTITION usage_ledger_old
            FOR VALUES FROM ('2024-01-01') TO ('2025-01-01')
        """)


def downgrade():
    op.execute("DROP TABLE usage_ledger CASCADE")
    op.execute("ALTER TABLE usage_ledger_old RENAME TO usage_ledger")
    op.create_index("ix_usage_ledger_company_created", "usage_ledger", ["company_id", "created_at"])
    op.create_index(
        "ix_usage_ledger_job_company_unique",
        "usage_ledger",
        ["job_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )
