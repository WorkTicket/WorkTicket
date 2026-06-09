import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorize import require_admin
from app.auth.dependencies import get_current_user
from app.billing.models import UsageLedger
from app.billing.schemas import (
    CostDriftResponse,
    CreditGrantRequest,
    CreditGrantResponse,
    UsageLedgerEntry,
    UsageLedgerListResponse,
)
from app.config import get_settings
from app.database import get_db, get_db_readonly
from app.jobs.models import User

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


@router.get("/usage", response_model=UsageLedgerListResponse)
async def get_usage_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_readonly),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(UsageLedger)
        .where(UsageLedger.company_id == current_user.company_id)
        .order_by(UsageLedger.created_at.desc())
    )

    count_q = select(sa_func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    entries = result.scalars().all()

    return UsageLedgerListResponse(
        entries=[UsageLedgerEntry.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/credits/grant", response_model=CreditGrantResponse)
async def grant_credit(
    payload: CreditGrantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.billing.credits import grant_credit as _grant

    result = await _grant(
        db=db,
        company_id=current_user.company_id,
        job_id=payload.job_id,
        amount_acu=payload.amount_acu,
        reason=payload.reason,
        granted_by=current_user.id,
    )
    return result


@router.post("/admin/refund", dependencies=[Depends(require_admin)])
async def admin_refund(
    job_id: UUID,
    amount_acu: float = Query(..., gt=0),
    reason: str = Query("manual_refund", min_length=1, max_length=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.billing.credits import grant_credit as _grant

    result = await _grant(
        db=db,
        company_id=current_user.company_id,
        job_id=job_id,
        amount_acu=amount_acu,
        reason=reason,
        granted_by=current_user.id,
    )
    return result


@router.post("/admin/reverse-charge", dependencies=[Depends(require_admin)])
async def admin_reverse_charge(
    ledger_entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UsageLedger).where(
            UsageLedger.id == ledger_entry_id,
            UsageLedger.company_id == current_user.company_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Usage ledger entry not found")

    from app.billing.credits import grant_credit as _grant

    amount_acu = float(abs(entry.cost_usd) / 0.01)
    result = await _grant(
        db=db,
        company_id=current_user.company_id,
        job_id=entry.job_id,
        amount_acu=amount_acu,
        reason=f"manual_reverse: {entry.id}",
        granted_by=current_user.id,
    )
    return result


@router.get("/cost-drift", response_model=CostDriftResponse)
async def get_cost_drift(
    hours: int = Query(168, ge=1, le=8760),
    db: AsyncSession = Depends(get_db_readonly),
    current_user: User = Depends(get_current_user),
):
    from app.billing.reconciliation import get_cost_drift as _drift

    return await _drift(db, current_user.company_id, hours=hours)
