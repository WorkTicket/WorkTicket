import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.estimates.models import Estimate, EstimateStatus

logger = logging.getLogger(__name__)

_ALLOWED_TRANSITIONS = {
    EstimateStatus.ai_pending: [EstimateStatus.draft],  # ai_pending -> draft via human review only
    EstimateStatus.draft: [EstimateStatus.in_review, EstimateStatus.approved],
    EstimateStatus.in_review: [EstimateStatus.approved, EstimateStatus.draft],
    EstimateStatus.approved: [EstimateStatus.sent, EstimateStatus.in_review],
    EstimateStatus.sent: [EstimateStatus.accepted, EstimateStatus.rejected],
    EstimateStatus.accepted: [],
    EstimateStatus.rejected: [EstimateStatus.draft],
}


def validate_transition(current: EstimateStatus, target: EstimateStatus) -> bool:
    allowed = _ALLOWED_TRANSITIONS.get(current, [])
    return target in allowed


async def transition_estimate(
    db: AsyncSession,
    estimate_id: UUID,
    company_id: UUID,
    target_status: EstimateStatus,
) -> bool:
    result = await db.execute(select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == company_id))
    estimate = result.scalar_one_or_none()
    if not estimate:
        logger.error("Estimate %s not found", estimate_id)
        return False

    current = EstimateStatus(estimate.status)
    if not validate_transition(current, target_status):
        logger.warning(
            "Invalid transition for estimate %s: %s -> %s",
            estimate_id,
            current.value,
            target_status.value,
        )
        return False

    now = datetime.now(UTC)
    estimate.status = target_status.value
    if target_status == EstimateStatus.approved:
        estimate.approved_at = now
    elif target_status == EstimateStatus.sent:
        estimate.sent_at = now
    await db.flush()

    logger.info("Estimate %s state: %s -> %s", estimate_id, current.value, target_status.value)
    return True
