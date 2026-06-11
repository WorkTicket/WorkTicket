import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorize import require_admin
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.jobs.models import Company, User
from app.notifications.encryption import decrypt_push_token, encrypt_push_token
from app.notifications.models import PushToken

logger = logging.getLogger(__name__)

router = APIRouter()


class PushTokenModel(BaseModel):
    push_token: str
    platform: str = "expo"


class PushTokenResponse(BaseModel):
    id: int
    user_id: str
    push_token: str
    platform: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/register-push-token")
async def register_push_token(
    payload: PushTokenModel,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted_token = encrypt_push_token(payload.push_token)
    result = await db.execute(
        select(PushToken).where(
            PushToken.user_id == current_user.id,
            PushToken.push_token == encrypted_token,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"status": "already_registered", "id": existing.id}

    company_check = await db.execute(select(Company).where(Company.id == current_user.company_id))
    if not company_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invalid company association")

    token = PushToken(
        user_id=current_user.id,
        company_id=current_user.company_id,
        push_token=encrypt_push_token(payload.push_token),
        platform=payload.platform,
    )
    db.add(token)
    await db.flush()
    await db.refresh(token)
    return {"status": "registered", "id": token.id}


@router.delete("/push-token/{token_id}", status_code=204)
async def unregister_push_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PushToken).where(
            PushToken.id == token_id,
            PushToken.user_id == current_user.id,
            PushToken.company_id == current_user.company_id,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Push token not found")
    await db.delete(token)
    await db.flush()
    return None


@router.post("/cleanup-stale-tokens", dependencies=[Depends(require_admin)])
async def cleanup_stale_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = datetime.now(UTC) - timedelta(days=90)
    result = await db.execute(
        delete(PushToken).where(
            PushToken.company_id == current_user.company_id,
            PushToken.created_at < cutoff,
        )
    )
    count = result.rowcount  # type: ignore[attr-defined]
    if count > 0:
        logger.info("Cleaned up %d stale push tokens for company %s", count, current_user.company_id)
    return {"cleaned": count}


@router.get("/delivery-status")
async def get_delivery_status(
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    from app.notifications.service import get_delivery_log

    log = await get_delivery_log(limit=limit, company_id=str(current_user.company_id))
    return {"delivery_log": log, "total_entries": len(log)}


@router.get("/push-tokens", response_model=dict)
async def list_push_tokens(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Base query
    query = select(PushToken).where(
        PushToken.user_id == current_user.id,
        PushToken.company_id == current_user.company_id,
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    tokens = result.scalars().all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size  # type: ignore[operator]

    return {
        "items": [
            PushTokenResponse(
                id=t.id,
                user_id=t.user_id,
                push_token=decrypt_push_token(t.push_token),
                platform=t.platform,
                created_at=t.created_at,
            )
            for t in tokens
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
