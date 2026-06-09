"""Add integration tables for Universal Business Migration Engine.

Revision ID: 039
Revises: 038
Create Date: 2026-06-08

Creates four tables for the integration & migration platform:
- integration_connections: Stores OAuth tokens and connection state per provider/tenant
- import_jobs: Tracks bulk import progress and status
- import_logs: Append-only log of every imported entity with external ID tracking
- mapping_rules: User-customizable field mapping between external systems and canonical schema
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("tenant", sa.String(255), nullable=False),
        sa.Column(
            "connection_status",
            sa.Enum("connected", "disconnected", "expired", "error", "pending", name="connection_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_integration_conn_company", "integration_connections", ["company_id"])
    op.create_index("ix_integration_conn_provider", "integration_connections", ["provider"])
    op.create_unique_constraint(
        "uq_connection_company_provider_tenant",
        "integration_connections",
        ["company_id", "provider", "tenant"],
    )
    op.create_foreign_key(
        "fk_integration_conn_company",
        "integration_connections",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "import_type",
            sa.Enum(
                "customers",
                "jobs",
                "work_orders",
                "invoices",
                "payments",
                "employees",
                "assets",
                "schedule_events",
                "locations",
                name="import_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "scanning", "ready", "in_progress", "completed", "partial", "failed", name="import_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("progress_pct", sa.Float, default=0.0),
        sa.Column("total_records", sa.Integer, default=0),
        sa.Column("imported_count", sa.Integer, default=0),
        sa.Column("skipped_count", sa.Integer, default=0),
        sa.Column("failed_count", sa.Integer, default=0),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_jobs_company", "import_jobs", ["company_id"])
    op.create_index("ix_import_jobs_provider", "import_jobs", ["provider"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_foreign_key(
        "fk_import_jobs_company", "import_jobs", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_import_jobs_connection",
        "import_jobs",
        "integration_connections",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "import_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("external_system", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("internal_id", sa.String(255), nullable=True),
        sa.Column(
            "entity_type",
            sa.Enum(
                "customers",
                "jobs",
                "work_orders",
                "invoices",
                "payments",
                "employees",
                "assets",
                "schedule_events",
                "locations",
                name="entity_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "result",
            sa.Enum("success", "skipped", "failed", "duplicate", name="import_result"),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("raw_data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_logs_company", "import_logs", ["company_id"])
    op.create_index("ix_import_logs_import_job", "import_logs", ["import_job_id"])
    op.create_index("ix_import_logs_external", "import_logs", ["external_system", "external_id"])
    op.create_index("ix_import_logs_entity_type", "import_logs", ["entity_type"])
    op.create_unique_constraint(
        "uq_import_logs_dedup",
        "import_logs",
        ["company_id", "external_system", "external_id", "entity_type"],
    )
    op.create_foreign_key(
        "fk_import_logs_company", "import_logs", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_import_logs_job", "import_logs", "import_jobs", ["import_job_id"], ["id"], ondelete="CASCADE"
    )

    op.create_table(
        "mapping_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        sa.Column("destination_field", sa.String(255), nullable=False),
        sa.Column("transformation_rule", sa.Text, nullable=True),
        sa.Column(
            "entity_type",
            sa.Enum(
                "customers",
                "jobs",
                "work_orders",
                "invoices",
                "payments",
                "employees",
                "assets",
                "schedule_events",
                "locations",
                name="mapping_entity_type",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_mapping_rules_company", "mapping_rules", ["company_id"])
    op.create_index("ix_mapping_rules_provider", "mapping_rules", ["provider"])
    op.create_unique_constraint(
        "uq_mapping_rule",
        "mapping_rules",
        ["company_id", "provider", "source_field", "destination_field", "entity_type"],
    )
    op.create_foreign_key(
        "fk_mapping_rules_company", "mapping_rules", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )

    for table in ("integration_connections", "import_jobs", "import_logs", "mapping_rules"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation ON {table} "
                "USING (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) "
                "WITH CHECK (company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation_bypass ON {table} "
                "USING (current_setting('app.bypass_rls', true) = 'true') "
                "WITH CHECK (current_setting('app.bypass_rls', true) = 'true')"
            )
        )
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def downgrade():
    for table in ("mapping_rules", "import_logs", "import_jobs", "integration_connections"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_bypass ON {table}"))

    op.drop_table("mapping_rules")
    op.drop_table("import_logs")
    op.drop_table("import_jobs")
    op.drop_table("integration_connections")

    op.execute("DROP TYPE IF EXISTS mapping_entity_type")
    op.execute("DROP TYPE IF EXISTS import_result")
    op.execute("DROP TYPE IF EXISTS entity_type")
    op.execute("DROP TYPE IF EXISTS import_status")
    op.execute("DROP TYPE IF EXISTS import_type")
    op.execute("DROP TYPE IF EXISTS connection_status")
