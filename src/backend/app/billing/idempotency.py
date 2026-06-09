import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="processing")
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "idempotency_key", name="uq_company_user_idempotency_key"),
        Index("ix_idempotency_keys_user_key", "user_id", "idempotency_key"),
        Index("ix_idempotency_keys_created_at", "created_at"),
        Index("ix_idempotency_keys_company_user", "company_id", "user_id"),
    )
