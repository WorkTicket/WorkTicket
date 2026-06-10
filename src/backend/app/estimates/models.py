import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.db.soft_delete import SoftDeleteMixin


def _utcnow():
    return datetime.now(UTC)


class EstimateStatus(enum.StrEnum):
    ai_pending = "ai_pending"  # AI-generated, requires human review before becoming draft
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"


class CompanyPricingBrain(Base):
    __tablename__ = "company_pricing_brains"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    trade_type = Column(String(50))
    labor_rates = Column(JSONB, default=dict)
    service_fee = Column(Float, default=0.0)
    minimum_charge_hours = Column(Float, default=1.5)
    rounding_rule = Column(String(20), default="30_min")
    markup_percent = Column(Float, default=25.0)
    emergency_multiplier = Column(Float, default=1.5)
    after_hours_multiplier = Column(Float, default=1.25)
    estimation_style = Column(String(30), default="range_conservative")
    historical_data_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (Index("ix_services_is_deleted_deleted_at", "is_deleted", "deleted_at"),)
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    name = Column(String(255), nullable=False)
    avg_time_hours = Column(Float, default=1.0)
    pricing_type = Column(String(20), default="hourly")
    flat_rate = Column(Float, nullable=True)
    material_assumptions = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Estimate(Base, SoftDeleteMixin):
    __tablename__ = "estimates"
    __table_args__ = (Index("ix_estimates_is_deleted_deleted_at", "is_deleted", "deleted_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default=EstimateStatus.draft.value)
    title = Column(String(255))
    description = Column(Text)
    subtotal = Column(Numeric(12, 2), default=Decimal("0.00"))
    tax = Column(Numeric(12, 2), default=Decimal("0.00"))
    total = Column(Numeric(12, 2), default=Decimal("0.00"))
    confidence_score = Column(Float, default=0.0)
    assumptions = Column(JSONB, default=list)
    notes = Column(Text)
    ai_generated = Column(Boolean, default=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    line_items = relationship(
        "EstimateLineItem",
        back_populates="estimate",
        cascade="all, delete-orphan",
        order_by="EstimateLineItem.sort_order",
    )


class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    item_type = Column(String(20), nullable=False)
    quantity = Column(Float, default=1.0)
    rate = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    sort_order = Column(Integer, default=0)
    ai_quantity = Column(Float, nullable=True)
    ai_rate = Column(Float, nullable=True)
    ai_total = Column(Float, nullable=True)
    override_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    estimate = relationship("Estimate", back_populates="line_items")


class HistoricalJobData(Base):
    __tablename__ = "historical_job_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id", ondelete="SET NULL"), nullable=True)
    service_type = Column(String(255))
    estimated_hours = Column(Float)
    actual_hours = Column(Float)
    estimated_cost = Column(Float)
    actual_cost = Column(Float)
    materials_used = Column(JSONB, default=list)
    final_invoice_amount = Column(Float)
    technician_notes = Column(Text)
    job_completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class EstimateAuditLog(Base):
    """Immutable audit trail for estimate operations.

    Records who created/approved/modified estimates, and when.
    Append-only — rows are never updated or deleted.
    """

    __tablename__ = "estimate_audit_logs"

    __table_args__ = (
        Index("ix_est_audit_logs_estimate_id", "estimate_id"),
        Index("ix_est_audit_logs_company_id", "company_id"),
        Index("ix_est_audit_logs_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estimate_id = Column(UUID(as_uuid=True), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    changed_by_user_id = Column(String(255), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
