from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def _utcnow():
    return datetime.now(UTC)


class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    push_token = Column(String(512), nullable=False)
    platform = Column(String(50), default="expo")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
