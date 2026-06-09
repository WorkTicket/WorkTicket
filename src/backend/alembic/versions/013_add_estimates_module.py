"""add estimates module (pricing brain, services, estimates, line items, historical data)

Revision ID: 013
Revises: 012
Create Date: 2026-05-23 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_pricing_brains",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("trade_type", sa.String(50), nullable=True),
        sa.Column("labor_rates", postgresql.JSONB, default=dict),
        sa.Column("service_fee", sa.Float, default=0.0),
        sa.Column("minimum_charge_hours", sa.Float, default=1.5),
        sa.Column("rounding_rule", sa.String(20), default="30_min"),
        sa.Column("markup_percent", sa.Float, default=25.0),
        sa.Column("emergency_multiplier", sa.Float, default=1.5),
        sa.Column("after_hours_multiplier", sa.Float, default=1.25),
        sa.Column("estimation_style", sa.String(30), default="range_conservative"),
        sa.Column("historical_data_enabled", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avg_time_hours", sa.Float, default=1.0),
        sa.Column("pricing_type", sa.String(20), default="hourly"),
        sa.Column("flat_rate", sa.Float, nullable=True),
        sa.Column("material_assumptions", postgresql.JSONB, default=list),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_services_company_id", "services", ["company_id"])

    op.create_table(
        "estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("subtotal", sa.Float, default=0.0),
        sa.Column("tax", sa.Float, default=0.0),
        sa.Column("total", sa.Float, default=0.0),
        sa.Column("confidence_score", sa.Float, default=0.0),
        sa.Column("assumptions", postgresql.JSONB, default=list),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("ai_generated", sa.Boolean, default=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_estimates_company_id", "estimates", ["company_id"])
    op.create_index("ix_estimates_job_id", "estimates", ["job_id"])
    op.create_index("ix_estimates_status", "estimates", ["status"])
    op.create_index("ix_estimates_company_status", "estimates", ["company_id", "status"])

    op.create_table(
        "estimate_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("estimates.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Float, default=1.0),
        sa.Column("rate", sa.Float, default=0.0),
        sa.Column("total", sa.Float, default=0.0),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("ai_quantity", sa.Float, nullable=True),
        sa.Column("ai_rate", sa.Float, nullable=True),
        sa.Column("ai_total", sa.Float, nullable=True),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_estimate_line_items_estimate_id", "estimate_line_items", ["estimate_id"])
    op.create_index("ix_estimate_line_items_company_id", "estimate_line_items", ["company_id"])

    op.create_table(
        "historical_job_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("estimates.id"), nullable=True),
        sa.Column("service_type", sa.String(255), nullable=True),
        sa.Column("estimated_hours", sa.Float, nullable=True),
        sa.Column("actual_hours", sa.Float, nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("actual_cost", sa.Float, nullable=True),
        sa.Column("materials_used", postgresql.JSONB, default=list),
        sa.Column("final_invoice_amount", sa.Float, nullable=True),
        sa.Column("technician_notes", sa.Text, nullable=True),
        sa.Column("job_completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_historical_job_data_company_id", "historical_job_data", ["company_id"])
    op.create_index("ix_historical_job_data_service_type", "historical_job_data", ["service_type"])


def downgrade() -> None:
    op.drop_index("ix_historical_job_data_service_type", table_name="historical_job_data")
    op.drop_index("ix_historical_job_data_company_id", table_name="historical_job_data")
    op.drop_table("historical_job_data")

    op.drop_index("ix_estimate_line_items_company_id", table_name="estimate_line_items")
    op.drop_index("ix_estimate_line_items_estimate_id", table_name="estimate_line_items")
    op.drop_table("estimate_line_items")

    op.drop_index("ix_estimates_company_status", table_name="estimates")
    op.drop_index("ix_estimates_status", table_name="estimates")
    op.drop_index("ix_estimates_job_id", table_name="estimates")
    op.drop_index("ix_estimates_company_id", table_name="estimates")
    op.drop_table("estimates")

    op.drop_index("ix_services_company_id", table_name="services")
    op.drop_table("services")

    op.drop_table("company_pricing_brains")
