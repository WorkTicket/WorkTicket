import uuid
from decimal import Decimal

from sqlalchemy import Column, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.config import get_settings
from app.database import Base


class UserDailyUsage(Base):
    __tablename__ = "user_daily_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    date = Column(String(10), nullable=False)
    acu_used = Column(Numeric(12, 4), default=Decimal("0.0"))
    job_count = Column(Numeric(12, 0), default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", "date", name="uq_user_daily_usage"),
        Index("ix_user_daily_usage_user_date", "user_id", "date"),
        Index("ix_user_daily_usage_company_id", "company_id"),
    )


def get_user_daily_acu_limit(company_id: str | None = None) -> float:
    """Get user daily ACU limit, potentially configurable per company or plan."""
    # For now, use a global setting but designed for future per-company/per-plan configuration
    settings = get_settings()
    return getattr(settings, "user_daily_acu_limit", 50.0)


def get_user_monthly_acu_limit(company_id: str | None = None) -> float:
    """Get user monthly ACU limit, potentially configurable per company or plan."""
    # For now, use a global setting but designed for future per-company/per-plan configuration
    settings = get_settings()
    return getattr(settings, "user_monthly_acu_limit", 500.0)
