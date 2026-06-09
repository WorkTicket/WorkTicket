import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import AIOutputSchema
from app.analytics import EVENT_JOB_APPROVED_WITH_CHANGES, EVENT_JOB_APPROVED_WITHOUT_CHANGES, EVENT_JOB_SENT, log_event
from app.auth.authorize import require_staff
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.estimates.models import CompanyPricingBrain
from app.jobs.models import AIOutput, Job, Quote, User
from app.notifications.models import PushToken

logger = logging.getLogger(__name__)

settings = get_settings()

router = APIRouter()


class QuoteGenerateResponse(BaseModel):
    quote_id: UUID
    job_id: UUID
    status: str
    total_amount: float
    line_items: dict


class QuoteListResponse(BaseModel):
    quotes: list[QuoteGenerateResponse]


@router.get("", response_model=QuoteListResponse)
async def list_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Quote).where(Quote.company_id == current_user.company_id).order_by(Quote.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    quotes = result.scalars().all()
    return QuoteListResponse(
        quotes=[
            QuoteGenerateResponse(
                quote_id=q.id,
                job_id=q.job_id,
                status=q.status,
                total_amount=q.total_amount or 0,
                line_items=json.loads(q.line_items or "{}"),
            )
            for q in quotes
        ]
    )


@router.post("/generate/{job_id}", response_model=QuoteGenerateResponse, dependencies=[Depends(require_staff)])
async def generate_quote(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_result = await db.execute(select(Job).where(Job.id == job_id, Job.company_id == current_user.company_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(AIOutput)
        .where(AIOutput.job_id == job_id, AIOutput.company_id == current_user.company_id)
        .order_by(AIOutput.created_at.desc())
    )
    ai_output = result.scalar_one_or_none()
    if not ai_output:
        raise HTTPException(status_code=400, detail="No AI output found. Process job first.")

    output_data = json.loads(ai_output.json_result)
    parsed = AIOutputSchema(**output_data)
    if parsed.is_fallback or parsed.confidence < 0.3:
        raise HTTPException(
            status_code=400,
            detail="AI analysis has low confidence or used fallback data. Review the analysis before generating a quote.",
        )
    labor_hours = output_data.get("estimated_hours", 0)
    # Use company-specific pricing brain rate, fall back to default
    brain_result = await db.execute(
        select(CompanyPricingBrain).where(CompanyPricingBrain.company_id == current_user.company_id)
    )
    brain = brain_result.scalar_one_or_none()
    if brain and brain.labor_rates and "default" in brain.labor_rates:
        hourly_rate = float(brain.labor_rates["default"])
    else:
        hourly_rate = settings.default_hourly_rate
    labor_total = labor_hours * hourly_rate

    line_items = {
        "labor": {
            "hours": labor_hours,
            "rate": hourly_rate,
            "total": round(labor_total, 2),
        },
        "materials": output_data.get("materials", []),
        "total": round(labor_total, 2),
        # Store AI confidence at generation time for approval validation
        "_ai_confidence": parsed.confidence,
    }

    quote = Quote(
        job_id=job_id,
        company_id=current_user.company_id,
        status="draft",
        total_amount=line_items["total"],
        line_items=json.dumps(line_items),
    )
    db.add(quote)
    await db.flush()
    await db.refresh(quote)

    return QuoteGenerateResponse(
        quote_id=quote.id,
        job_id=job_id,
        status=quote.status,
        total_amount=line_items["total"],
        line_items=line_items,
    )


@router.get("/{quote_id}", response_model=QuoteGenerateResponse)
async def get_quote(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.company_id == current_user.company_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return QuoteGenerateResponse(
        quote_id=quote.id,
        job_id=quote.job_id,
        status=quote.status,
        total_amount=quote.total_amount or 0,
        line_items=json.loads(quote.line_items or "{}"),
    )


@router.post("/{quote_id}/approve", dependencies=[Depends(require_staff)])
async def approve_quote(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.company_id == current_user.company_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    line_items_data = json.loads(quote.line_items or "{}")
    stored_confidence = line_items_data.get("_ai_confidence")
    if stored_confidence is not None and stored_confidence < 0.3:
        raise HTTPException(
            status_code=400,
            detail="AI analysis confidence was below threshold at quote generation time. Please regenerate the quote.",
        )

    quote.status = "approved"
    import datetime

    quote.approved_at = datetime.datetime.now(datetime.UTC)
    await db.flush()

    try:
        from app.notifications.service import notify_quote_approved

        job_result = await db.execute(
            select(Job).where(Job.id == quote.job_id, Job.company_id == current_user.company_id)
        )
        job = job_result.scalar_one_or_none()
        if job and job.technician_id:
            token_result = await db.execute(
                select(PushToken).where(
                    PushToken.user_id == job.technician_id,
                    PushToken.company_id == job.company_id,
                )
            )
            tokens = token_result.scalars().all()
            if tokens:
                await notify_quote_approved(str(quote.job_id), [(t.id, t.push_token) for t in tokens])
    except Exception as e:
        logger.warning("Failed to send approval notification: %s", e)

    logger.info("Quote %s approved by user %s", quote_id, current_user.id)

    from app.analytics.events import AnalyticsEvent

    edit_check = await db.execute(
        select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.job_id == quote.job_id,
            AnalyticsEvent.event_name == "ai_output_edited",
            AnalyticsEvent.company_id == current_user.company_id,
        )
    )
    was_edited = (edit_check.scalar() or 0) > 0
    approval_event = EVENT_JOB_APPROVED_WITH_CHANGES if was_edited else EVENT_JOB_APPROVED_WITHOUT_CHANGES

    await log_event(
        event_name=approval_event,
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(quote.job_id),
        metadata={"quote_id": str(quote.id), "total_amount": quote.total_amount, "was_edited": was_edited},
    )

    return {"status": "approved", "quote_id": str(quote.id)}


@router.post("/{quote_id}/send", dependencies=[Depends(require_staff)])
async def send_quote(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.company_id == current_user.company_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "approved":
        raise HTTPException(status_code=400, detail="Quote must be approved before sending")

    quote.status = "sent"
    await db.flush()

    await log_event(
        event_name=EVENT_JOB_SENT,
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(quote.job_id),
        metadata={"quote_id": str(quote.id), "total_amount": float(quote.total_amount) if quote.total_amount else 0},
    )

    return {"status": "sent", "quote_id": str(quote.id)}


@router.delete("/{quote_id}", status_code=204, dependencies=[Depends(require_staff)])
async def delete_quote(
    quote_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.company_id == current_user.company_id))
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    await db.delete(quote)
    await db.flush()
    return None
