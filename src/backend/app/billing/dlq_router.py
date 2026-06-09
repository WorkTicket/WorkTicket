import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.billing.dlq_monitor import (
    cleanup_expired_dlq,
    get_dlq_by_failure_category,
    get_dlq_entries,
    get_dlq_summary,
)
from app.database import get_db
from app.jobs.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dlq/summary")
async def dlq_summary(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can view DLQ")
    return await get_dlq_summary(db, company_id=str(current_user.company_id), hours=hours)


@router.get("/dlq/entries")
async def dlq_entries(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can view DLQ")
    return await get_dlq_entries(db, company_id=str(current_user.company_id), limit=limit, offset=offset)


@router.get("/dlq/categories")
async def dlq_categories(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can view DLQ")
    return await get_dlq_by_failure_category(db, hours=hours)


@router.post("/dlq/cleanup-expired")
async def dlq_cleanup_expired(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can clean up DLQ")
    count = await cleanup_expired_dlq(db)
    return {"cleaned": count}


@router.post("/dlq/replay/{dead_letter_id}")
async def dlq_replay(
    dead_letter_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """MEDIUM-2 FIX: Manually trigger a DLQ replay for a specific dead letter entry.
    Previously operators had to connect to the beat container and call
    retry_dead_letter_job.delay(...) manually.
    """
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can replay DLQ entries")
    from app.billing.tasks import _retry_dead_letter_job

    result = await _retry_dead_letter_job(dead_letter_id)
    return result
