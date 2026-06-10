import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

logger = logging.getLogger(__name__)


class EstimateAuditSnapshot(Base):
    __tablename__ = "estimate_audit_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estimate_id = Column(UUID(as_uuid=True), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    user_id = Column(String(255), nullable=False)
    snapshot_data = Column(JSONB, nullable=False)
    previous_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    diff_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("ix_estimate_audit_estimate_id", "estimate_id"),
        Index("ix_estimate_audit_company_id", "company_id"),
        Index("ix_estimate_audit_event_type", "event_type"),
        Index("ix_estimate_audit_created_at", "created_at"),
    )


async def record_snapshot(
    db: AsyncSession,
    estimate_id: uuid.UUID,
    company_id: uuid.UUID,
    event_type: str,
    user_id: str,
    snapshot_data: dict,
    previous_snapshot_id: uuid.UUID | None = None,
    diff_data: dict | None = None,
) -> EstimateAuditSnapshot:
    entry = EstimateAuditSnapshot(
        estimate_id=estimate_id,
        company_id=company_id,
        event_type=event_type,
        user_id=user_id,
        snapshot_data=snapshot_data,
        previous_snapshot_id=previous_snapshot_id,
        diff_data=diff_data,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_snapshots(
    db: AsyncSession,
    estimate_id: uuid.UUID,
    company_id: uuid.UUID,
    limit: int = 100,
) -> list[EstimateAuditSnapshot]:
    result = await db.execute(
        select(EstimateAuditSnapshot)
        .where(
            EstimateAuditSnapshot.estimate_id == estimate_id,
            EstimateAuditSnapshot.company_id == company_id,
        )
        .order_by(EstimateAuditSnapshot.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_snapshot(
    db: AsyncSession,
    estimate_id: uuid.UUID,
    company_id: uuid.UUID,
) -> EstimateAuditSnapshot | None:
    result = await db.execute(
        select(EstimateAuditSnapshot)
        .where(
            EstimateAuditSnapshot.estimate_id == estimate_id,
            EstimateAuditSnapshot.company_id == company_id,
        )
        .order_by(EstimateAuditSnapshot.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def build_estimate_snapshot(estimate, line_items: list) -> dict:
    return {
        "status": estimate.status,
        "title": estimate.title,
        "description": estimate.description,
        "subtotal": estimate.subtotal,
        "tax": estimate.tax,
        "total": estimate.total,
        "confidence_score": estimate.confidence_score,
        "assumptions": estimate.assumptions,
        "notes": estimate.notes,
        "ai_generated": estimate.ai_generated,
        "line_items": [
            {
                "name": li.name,
                "item_type": li.item_type,
                "quantity": li.quantity,
                "rate": li.rate,
                "total": li.total,
                "sort_order": li.sort_order,
                "ai_quantity": li.ai_quantity,
                "ai_rate": li.ai_rate,
                "ai_total": li.ai_total,
                "override_reason": li.override_reason,
            }
            for li in line_items
        ],
    }


def compute_snapshot_diff(previous: dict, current: dict) -> dict:
    diffs = {}
    scalar_fields = ["title", "description", "subtotal", "tax", "total", "confidence_score", "notes", "status"]
    for field in scalar_fields:
        pv = previous.get(field)
        cv = current.get(field)
        if pv != cv:
            diffs[field] = {"from": pv, "to": cv}
    prev_items = {li["sort_order"]: li for li in previous.get("line_items", [])}
    curr_items = {li["sort_order"]: li for li in current.get("line_items", [])}
    item_diffs = []
    all_keys = set(prev_items.keys()) | set(curr_items.keys())
    for k in sorted(all_keys):
        if k in prev_items and k in curr_items:
            p = prev_items[k]
            c = curr_items[k]
            item_changes = {}
            for f in ["name", "item_type", "quantity", "rate", "total"]:
                if p.get(f) != c.get(f):
                    item_changes[f] = {"from": p.get(f), "to": c.get(f)}
            if item_changes:
                item_diffs.append({"sort_order": k, "changes": item_changes})
        elif k in prev_items:
            item_diffs.append({"sort_order": k, "changes": {"_action": "removed", "from": prev_items[k]}})
        else:
            item_diffs.append({"sort_order": k, "changes": {"_action": "added", "to": curr_items[k]}})
    if item_diffs:
        diffs["line_items"] = item_diffs
    if previous.get("ai_generated") != current.get("ai_generated"):
        diffs["ai_generated"] = {"from": previous.get("ai_generated"), "to": current.get("ai_generated")}
    return diffs
