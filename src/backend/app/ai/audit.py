import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import AsyncSessionLocal, Base

logger = logging.getLogger(__name__)

_AUDIT_SIGNING_KEY = os.getenv("AUDIT_SIGNING_KEY", "")


def _sign_audit_event(event_id: str, timestamp: str, source: str, payload_hash: str) -> str:
    if not _AUDIT_SIGNING_KEY:
        return ""
    canonical = f"{event_id}|{timestamp}|{source}|{payload_hash}"
    return hmac.new(
        _AUDIT_SIGNING_KEY.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _hash_payload(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AIAuditLog(Base):
    __tablename__ = "ai_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String(255), nullable=True)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    request_type = Column(String(50), nullable=False)
    model_used = Column(String(100), nullable=True)
    latency_ms = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    circuit_state = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)
    queue_wait_ms = Column(Float, nullable=True)
    cpu_time_ms = Column(Float, nullable=True)
    memory_estimate_bytes = Column(BigInteger, nullable=True)
    queue_pressure_at_time = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    event_signature = Column(String(64), nullable=True)
    payload_hash = Column(String(64), nullable=True)


_AUDIT_RETENTION_DAYS = 90


async def cleanup_old_audit_logs():
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import delete

        cutoff = datetime.now(UTC) - timedelta(days=_AUDIT_RETENTION_DAYS)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AIAuditLog).where(AIAuditLog.created_at < cutoff))
            await db.commit()
            logger.info("Cleaned up audit logs older than %d days", _AUDIT_RETENTION_DAYS)
    except Exception as e:
        logger.error("Failed to cleanup audit logs: %s", e)


class AuditService:
    @staticmethod
    async def log(
        request_type: str,
        latency_ms: float,
        success: bool,
        company_id: str,
        user_id: str | None = None,
        job_id: str | None = None,
        model_used: str | None = None,
        circuit_state: str | None = None,
        error_message: str | None = None,
        queue_wait_ms: float | None = None,
        cpu_time_ms: float | None = None,
        memory_estimate_bytes: int | None = None,
        queue_pressure_at_time: int | None = None,
    ):
        try:
            async with AsyncSessionLocal() as db:
                event_id = str(uuid.uuid4())
                timestamp = datetime.now(UTC).isoformat()
                payload = {
                    "company_id": company_id,
                    "user_id": user_id,
                    "request_type": request_type,
                    "success": success,
                }
                payload_hash = _hash_payload(payload)
                event_signature = _sign_audit_event(event_id, timestamp, "ai_gateway", payload_hash)

                entry = AIAuditLog(
                    id=event_id,
                    company_id=company_id,
                    user_id=user_id,
                    job_id=job_id,
                    request_type=request_type,
                    model_used=model_used,
                    latency_ms=round(latency_ms, 2),
                    success=success,
                    circuit_state=circuit_state,
                    error_message=error_message[:1000] if error_message else None,
                    queue_wait_ms=round(queue_wait_ms, 2) if queue_wait_ms else None,
                    cpu_time_ms=round(cpu_time_ms, 2) if cpu_time_ms else None,
                    memory_estimate_bytes=memory_estimate_bytes,
                    queue_pressure_at_time=queue_pressure_at_time,
                    event_signature=event_signature or None,
                    payload_hash=payload_hash,
                )
                db.add(entry)
                await db.commit()
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)

    @staticmethod
    async def get_recent(limit: int = 100, request_type: str | None = None) -> list:
        from sqlalchemy import desc, select

        async with AsyncSessionLocal() as db:
            q = select(AIAuditLog).order_by(desc(AIAuditLog.created_at))
            if request_type:
                q = q.where(AIAuditLog.request_type == request_type)
            q = q.limit(limit)
            result = await db.execute(q)
            return result.scalars().all()

    @staticmethod
    async def get_failure_rate(minutes: int = 60) -> dict:
        from datetime import datetime, timedelta

        from sqlalchemy import func, select

        async with AsyncSessionLocal() as db:
            cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
            total = await db.execute(select(func.count(AIAuditLog.id)).where(AIAuditLog.created_at >= cutoff))
            total_count = total.scalar() or 0
            failures = await db.execute(
                select(func.count(AIAuditLog.id)).where(
                    AIAuditLog.created_at >= cutoff,
                    AIAuditLog.success == False,  # noqa: E712
                )
            )
            failure_count = failures.scalar() or 0
            return {
                "total_requests": total_count,
                "failures": failure_count,
                "failure_rate": round(failure_count / total_count, 4) if total_count > 0 else 0,
                "window_minutes": minutes,
            }

    @staticmethod
    async def verify_signature(entry: AIAuditLog) -> bool:
        if not entry.event_signature or not entry.payload_hash:
            return True
        payload = {
            "company_id": str(entry.company_id),
            "user_id": entry.user_id,
            "request_type": entry.request_type,
            "success": entry.success,
        }
        expected_hash = _hash_payload(payload)
        if expected_hash != entry.payload_hash:
            logger.warning("Audit entry %s: payload hash mismatch", entry.id)
            return False
        expected_sig = _sign_audit_event(
            str(entry.id), entry.created_at.isoformat() if entry.created_at else "", "ai_gateway", expected_hash
        )
        if expected_sig != entry.event_signature:
            logger.warning("Audit entry %s: signature mismatch", entry.id)
            return False
        return True


audit = AuditService()
