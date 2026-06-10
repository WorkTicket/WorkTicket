import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.db.soft_delete import SoftDeleteMixin


def _utcnow():
    return datetime.now(UTC)


class UserRole(enum.StrEnum):
    owner = "owner"
    dispatcher = "dispatcher"
    technician = "technician"
    admin = "admin"


class JobStatus(enum.StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class AIProcessingState(enum.StrEnum):
    none = "none"
    queued = "queued"
    reserved = "reserved"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    compensated = "compensated"


class Company(Base):
    __tablename__ = "companies"

    __table_args__ = (
        Index("ix_companies_stripe_customer_id", "stripe_customer_id"),
        Index("ix_companies_stripe_subscription_id", "stripe_subscription_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    subscription_plan = Column(String(50), default="free")
    trade_type = Column(String(50), nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    users = relationship("User", back_populates="company")


class User(Base, SoftDeleteMixin):
    __tablename__ = "users"
    __allow_unmapped__ = True

    id = Column(String(255), primary_key=True)  # Clerk user ID format: "user_<random>"
    user_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    clerk_user_id = Column(String(255), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    encrypted_email = Column(sa.Text, nullable=True)
    encrypted_name = Column(sa.Text, nullable=True)
    role = Column(String(50), default=UserRole.technician.value)
    is_active = Column(Boolean, default=True)
    token_version = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    company = relationship("Company", back_populates="users")
    jobs: list["Job"] = relationship("Job", back_populates="technician")

    @property
    def safe_email(self) -> str:
        if self.encrypted_email:
            from app.security.encryption import decrypt_field_from_storage

            return decrypt_field_from_storage(self.encrypted_email) or self.email
        return self.email

    @safe_email.setter
    def safe_email(self, value: str):
        from app.security.encryption import encrypt_field_for_storage

        encrypted = encrypt_field_for_storage(value)
        if encrypted != value:
            self.encrypted_email = encrypted
        self.email = value

    @property
    def safe_name(self) -> str:
        if self.encrypted_name:
            from app.security.encryption import decrypt_field_from_storage

            return decrypt_field_from_storage(self.encrypted_name) or self.name
        return self.name

    @safe_name.setter
    def safe_name(self, value: str):
        from app.security.encryption import encrypt_field_for_storage

        encrypted = encrypt_field_for_storage(value)
        if encrypted != value:
            self.encrypted_name = encrypted
        self.name = value


class Customer(Base, SoftDeleteMixin):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_is_deleted_deleted_at", "is_deleted", "deleted_at"),)
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(Text)
    encrypted_email = Column(sa.Text, nullable=True)
    encrypted_phone = Column(sa.Text, nullable=True)
    encrypted_name = Column(sa.Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    @property
    def safe_email(self) -> str:
        if self.encrypted_email:
            from app.security.encryption import decrypt_field_from_storage

            return decrypt_field_from_storage(self.encrypted_email) or self.email
        return self.email

    @safe_email.setter
    def safe_email(self, value: str):
        from app.security.encryption import encrypt_field_for_storage

        encrypted = encrypt_field_for_storage(value)
        if encrypted != value:
            self.encrypted_email = encrypted
        self.email = value

    @property
    def safe_phone(self) -> str:
        if self.encrypted_phone:
            from app.security.encryption import decrypt_field_from_storage

            return decrypt_field_from_storage(self.encrypted_phone) or self.phone
        return self.phone

    @safe_phone.setter
    def safe_phone(self, value: str):
        from app.security.encryption import encrypt_field_for_storage

        encrypted = encrypt_field_for_storage(value)
        if encrypted != value:
            self.encrypted_phone = encrypted
        self.phone = value

    @property
    def safe_name(self) -> str:
        if self.encrypted_name:
            from app.security.encryption import decrypt_field_from_storage

            return decrypt_field_from_storage(self.encrypted_name) or self.name
        return self.name

    @safe_name.setter
    def safe_name(self, value: str):
        from app.security.encryption import encrypt_field_for_storage

        encrypted = encrypt_field_for_storage(value)
        if encrypted != value:
            self.encrypted_name = encrypted
        self.name = value


class Job(Base, SoftDeleteMixin):
    __tablename__ = "jobs"
    __allow_unmapped__ = True
    __table_args__ = (
        Index("ix_jobs_is_deleted_deleted_at", "is_deleted", "deleted_at"),
        Index("ix_jobs_ai_state_updated", "ai_processing_state", "ai_processing_updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=False)
    technician_id = Column(String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    status = Column(String(50), default=JobStatus.pending.value)
    ai_processing_state = Column(String(20), default=AIProcessingState.none.value)
    ai_processing_updated_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, default=0)
    compensation_attempts = Column(Integer, default=0)
    state_cycle_counter = Column(Integer, default=0)
    state_cycle_reset_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_time = Column(DateTime(timezone=True))
    description = Column(Text)
    address = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    technician: Optional["User"] = relationship("User", back_populates="jobs")
    media: list["JobMedia"] = relationship("JobMedia", back_populates="job")
    ai_outputs: list["AIOutput"] = relationship("AIOutput", back_populates="job")


class JobMedia(Base):
    __tablename__ = "job_media"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    storage_url = Column(String(1024), nullable=False)
    storage_key = Column(String(1024), nullable=True)
    thumbnail_url = Column(String(1024))
    mime_type = Column(String(50))
    file_size = Column(Float)
    ai_processed = Column(Boolean, default=False)
    upload_signature = Column(String(128), nullable=True)  # H6: HMAC binding upload to pre-signed URL
    content_hash = Column(String(128), nullable=True)  # H6: SHA-256 of uploaded content for integrity
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    job: Optional["Job"] = relationship("Job", back_populates="media")


AI_OUTPUT_UNIQUE_CONSTRAINT_NAME = "uq_ai_output_job_type_company"


class AIOutput(Base):
    __tablename__ = "ai_outputs"
    __allow_unmapped__ = True

    __table_args__ = (
        UniqueConstraint("job_id", "output_type", "company_id", name=AI_OUTPUT_UNIQUE_CONSTRAINT_NAME),
        Index("ix_ai_outputs_company_job_created", "company_id", "job_id", sa.text("created_at DESC")),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    output_type = Column(String(50), nullable=False)
    json_result = Column(Text, nullable=False)
    confidence_score = Column(Float)
    model_used = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    job = relationship("Job", back_populates="ai_outputs")


class AIOutputFeedback(Base):
    __tablename__ = "ai_output_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_output_id = Column(UUID(as_uuid=True), ForeignKey("ai_outputs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    modifications = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Quote(Base, SoftDeleteMixin):
    __tablename__ = "quotes"
    __table_args__ = (Index("ix_quotes_is_deleted_deleted_at", "is_deleted", "deleted_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="draft")
    total_amount = Column(Numeric(12, 2))
    line_items = Column(Text)
    pdf_url = Column(String(1024))
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class JobAuditLog(Base):
    """Immutable audit trail for job status and field changes (D-1 fix).

    Records who changed what field, from what value to what value, and when.
    Append-only — rows are never updated or deleted. Enables tracking of
    unauthorized status changes and provides a complete audit history per job.
    """

    __tablename__ = "job_audit_logs"

    __table_args__ = (
        Index("ix_job_audit_logs_job_id", "job_id"),
        Index("ix_job_audit_logs_company_id", "company_id"),
        Index("ix_job_audit_logs_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    changed_by_user_id = Column(String(255), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class UserAuditLog(Base):
    """Immutable audit trail for user management operations.

    Records who activated/deactivated/changed roles, and when.
    Append-only — rows are never updated or deleted.
    """

    __tablename__ = "user_audit_logs"

    __table_args__ = (
        Index("ix_user_audit_logs_target_user", "target_user_id"),
        Index("ix_user_audit_logs_company_id", "company_id"),
        Index("ix_user_audit_logs_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_user_id = Column(String(255), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    changed_by_user_id = Column(String(255), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
