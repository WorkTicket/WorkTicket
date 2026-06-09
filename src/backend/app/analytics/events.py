import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import AsyncSessionLocal, Base

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {
    "description",
    "address",
    "customer_name",
    "email",
    "phone",
    "pricing_data",
    "hourly_rate",
    "original_prompt",
}


def redact_metadata(metadata: dict) -> dict:
    if not metadata:
        return metadata
    return {k: ("[REDACTED]" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v) for k, v in metadata.items()}


EVENT_JOB_CREATED = "job_created"
EVENT_JOB_COMPLETED = "job_completed"
EVENT_INVOICE_CREATED = "invoice_created"
EVENT_AI_OUTPUT_GENERATED = "ai_output_generated"
EVENT_AI_OUTPUT_VIEWED = "ai_output_viewed"
EVENT_AI_OUTPUT_EDITED = "ai_output_edited"
EVENT_JOB_APPROVED_WITHOUT_CHANGES = "job_approved_without_changes"
EVENT_JOB_APPROVED_WITH_CHANGES = "job_approved_with_changes"
EVENT_JOB_SENT = "job_sent"
EVENT_JOB_REOPENED = "job_reopened"
EVENT_VOICE_USED = "voice_used"
EVENT_PHOTO_UPLOADED = "photo_uploaded"
EVENT_OFFLINE_SYNC_COMPLETED = "offline_sync_completed"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    client_timestamp = Column(DateTime, nullable=True)
    event_name = Column(String(100), nullable=False)
    user_id = Column(String(255), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_analytics_events_event_name", "event_name"),
        Index("ix_analytics_events_user_id", "user_id"),
        Index("ix_analytics_events_company_id", "company_id"),
        Index("ix_analytics_events_timestamp", "timestamp"),
        Index("ix_analytics_events_job_id", "job_id"),
    )


async def log_event(
    event_name: str,
    user_id: str,
    company_id: str,
    job_id: str | None = None,
    metadata: dict | None = None,
    client_timestamp: datetime | None = None,
):
    try:
        async with AsyncSessionLocal() as db:
            entry = AnalyticsEvent(
                event_name=event_name,
                user_id=user_id,
                company_id=company_id,
                job_id=job_id,
                event_metadata=redact_metadata(metadata or {}),
                client_timestamp=client_timestamp,
            )
            db.add(entry)
            await db.commit()
    except Exception as e:
        logger.error("Failed to log analytics event %s: %s", event_name, e)


_ANALYTICS_RETENTION_DAYS = 365


async def cleanup_old_analytics_events():
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import delete

        cutoff = datetime.now(UTC) - timedelta(days=_ANALYTICS_RETENTION_DAYS)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.timestamp < cutoff))
            await db.commit()
            logger.info("Cleaned up analytics events older than %d days", _ANALYTICS_RETENTION_DAYS)
    except Exception as e:
        logger.error("Failed to cleanup analytics events: %s", e)
