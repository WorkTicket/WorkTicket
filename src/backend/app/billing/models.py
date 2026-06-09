import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


class BillingAccount(Base):
    __tablename__ = "billing_accounts"

    __table_args__ = (
        Index("ix_billing_accounts_stripe_subscription_id", "stripe_subscription_id"),
        Index("ix_billing_accounts_is_deleted_deleted_at", "is_deleted", "deleted_at"),
    )
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_deleted = Column(sa.Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    plan = Column(String(50), default="free")
    monthly_quota_acu = Column(Numeric(12, 4), default=15.0)
    used_acu = Column(Numeric(12, 4), default=0.0)
    reserved_acu = Column(Numeric(12, 4), default=0.0)
    acu_debt = Column(Numeric(12, 4), default=0.0)  # Tracks negative reserved_acu from reconciliation errors
    max_acu_debt = Column(Numeric(12, 4), default=500.0)  # H3: Hard cap on ACU debt
    overage_enabled = Column(Boolean, default=False)
    ai_disabled = Column(Boolean, default=False)
    ai_disabled_reason = Column(
        String(50), nullable=True
    )  # H-8: tracks why AI was disabled (payment_failed, abuse, manual)
    risk_score = Column(Integer, default=0)
    temp_quota_multiplier = Column(Numeric(6, 4), default=Decimal("1.0000"), nullable=False)
    stripe_subscription_id = Column(String(255), nullable=True)
    reservation_heartbeat_at = Column(DateTime, nullable=True)
    billing_period_start = Column(DateTime, nullable=True)
    billing_period_end = Column(DateTime, nullable=True)
    reset_at = Column(DateTime, nullable=True)
    last_reconciled = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    storage_quota_bytes = Column(sa.BigInteger, default=5 * 1024**3, nullable=False)  # 5GB default
    used_storage_bytes = Column(sa.BigInteger, default=0, nullable=False)
    version = Column(Integer, default=0, nullable=False)


class UsageLedger(Base):
    __tablename__ = "usage_ledger"

    __table_args__ = (
        Index("ix_usage_ledger_company_created", "company_id", "created_at"),
        # Partial unique index on (job_id, company_id) — created in
        # migration 020. Prevents duplicate ledger entries per job (C2 fix).
        Index(
            "ix_usage_ledger_job_company_unique",
            "job_id",
            "company_id",
            unique=True,
            postgresql_where=sa.text("job_id IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    text_units = Column(Integer, default=0)
    vision_units = Column(Integer, default=0)
    audio_units = Column(Integer, default=0)
    cost_usd = Column(Numeric(12, 6), default=0.0)
    estimated_cost_usd = Column(Numeric(12, 6), default=0.0)
    model_used = Column(String(100), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    is_credit = Column(Boolean, default=False)
    credit_reason = Column(String(255), nullable=True)
    original_job_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(String(255), nullable=True)
    billing_period = Column(String(7), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class AIJobEstimate(Base):
    __tablename__ = "ai_job_estimates"

    __table_args__ = (UniqueConstraint("company_id", "job_id", name="uq_ai_job_estimate_company_job"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    estimated_text_cost = Column(Numeric(12, 6), default=0.0)
    estimated_vision_cost = Column(Numeric(12, 6), default=0.0)
    estimated_audio_cost = Column(Numeric(12, 6), default=0.0)
    estimated_total_cost = Column(Numeric(12, 6), default=0.0)
    approved = Column(Boolean, default=False)
    rejected_reason = Column(String(255), nullable=True)
    billing_period = Column(String(7), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    __table_args__ = (Index("ix_stripe_webhook_events_company_event", "company_id", "event_type"),)

    id = Column(String(255), primary_key=True)
    event_type = Column(String(100), nullable=False)
    company_id = Column(
        UUID(as_uuid=True), nullable=True, comment="nullable for dedup entries, populated after processing"
    )
    processed_at = Column(DateTime, default=_utcnow)


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        Index("ix_invoices_company_id", "company_id"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_created_at", "created_at"),
        Index("ix_invoices_company_status", "company_id", "status"),
        Index("ix_invoices_is_deleted_deleted_at", "is_deleted", "deleted_at"),
    )
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    is_deleted = Column(sa.Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    line_items = Column(JSONB, nullable=False)
    subtotal = Column(Numeric(12, 2), default=0.0)
    tax = Column(Numeric(12, 2), default=0.0)
    total = Column(Numeric(12, 2), default=0.0)
    status = Column(String(20), default="draft")  # draft, sent, paid, void
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class BillingAuditLog(Base):
    """Immutable audit trail for billing account modifications (R-1 fix).

    Records who changed what field, from what value to what value, and when.
    Append-only — rows are never updated or deleted. Enables detection of
    unauthorized billing modifications and provides compliance audit history.
    """

    __tablename__ = "billing_audit_logs"

    __table_args__ = (
        Index("ix_billing_audit_logs_company_id", "company_id"),
        Index("ix_billing_audit_logs_account_id", "billing_account_id"),
        Index("ix_billing_audit_logs_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    billing_account_id = Column(UUID(as_uuid=True), nullable=False)
    changed_by_user_id = Column(String(255), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
