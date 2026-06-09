import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rate_limiter import rate_limiter
from app.analytics import log_event
from app.auth.authorize import require_admin, require_staff
from app.auth.dependencies import get_current_user
from app.billing.cost_estimator import estimate_job_cost
from app.billing.quota_engine import quota_engine
from app.database import get_db
from app.estimates.audit import (
    build_estimate_snapshot,
    compute_snapshot_diff,
    get_latest_snapshot,
    get_snapshots,
    record_snapshot,
)
from app.estimates.engine import generate_estimate_ai, get_historical_insights
from app.estimates.models import (
    CompanyPricingBrain,
    Estimate,
    EstimateLineItem,
    EstimateStatus,
    HistoricalJobData,
    Service,
)
from app.estimates.schemas import (
    CompanyPricingBrainResponse,
    CompanyPricingBrainUpdate,
    EstimateGenerateRequest,
    EstimateListResponse,
    EstimateResponse,
    EstimateUpdateRequest,
    HistoricalJobRecord,
    ServiceCreate,
    ServiceResponse,
)
from app.estimates.state_machine import EstimateStatus as SMStatus
from app.estimates.state_machine import transition_estimate
from app.jobs.models import Customer, Job, User
from app.pricing.engine import _round_currency, recompute_estimate, recompute_line_item, validate_estimate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def generate_estimate(
    req: EstimateGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed, reason = await rate_limiter.check_all(
        user_id=current_user.id,
        company_id=str(current_user.company_id),
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    import uuid as _uuid

    cost_est = estimate_job_cost(image_count=0, has_audio=False)
    quota_result = await quota_engine.check_and_reserve(
        db=db,
        company_id=current_user.company_id,
        estimated_cost_usd=cost_est.total_cost * 0.5,
        job_id=_uuid.uuid4(),
        user_id=str(current_user.id) if hasattr(current_user, "id") else None,
    )
    if not quota_result.allowed:
        raise HTTPException(status_code=402, detail=f"Quota exceeded: {quota_result.reason}")

    job = None
    if req.job_id:
        result = await db.execute(select(Job).where(Job.id == req.job_id, Job.company_id == current_user.company_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    brain_result = await db.execute(
        select(CompanyPricingBrain).where(CompanyPricingBrain.company_id == current_user.company_id)
    )
    brain = brain_result.scalar_one_or_none()
    if not brain:
        raise HTTPException(status_code=400, detail="Company pricing brain not configured. Complete onboarding first.")

    services_result = await db.execute(select(Service).where(Service.company_id == current_user.company_id))
    services = services_result.scalars().all()
    service_catalog = [
        {"name": s.name, "avg_time_hours": s.avg_time_hours, "pricing_type": s.pricing_type} for s in services
    ]

    customer_info = None
    if req.customer_id:
        cust_result = await db.execute(
            select(Customer).where(Customer.id == req.customer_id, Customer.company_id == current_user.company_id)
        )
        customer = cust_result.scalar_one_or_none()
        if customer:
            customer_info = f"Name: {customer.name}"
            if customer.phone:
                customer_info += f", Phone: {customer.phone}"
            if customer.address:
                customer_info += f", Address: {customer.address}"

    job_description = req.description or (job.description if job else "")
    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required")

    company_pricing = {
        "trade_type": brain.trade_type,
        "labor_rates": brain.labor_rates,
        "service_fee": brain.service_fee,
        "minimum_charge_hours": brain.minimum_charge_hours,
        "rounding_rule": brain.rounding_rule,
        "markup_percent": brain.markup_percent,
        "emergency_multiplier": brain.emergency_multiplier,
        "after_hours_multiplier": brain.after_hours_multiplier,
        "estimation_style": brain.estimation_style,
    }

    historical_insights = None
    if brain.historical_data_enabled:
        historical_insights = await get_historical_insights(db, current_user.company_id)

    ai_result = await generate_estimate_ai(
        job_description=job_description,
        company_pricing=company_pricing,
        customer_info=customer_info,
        service_catalog=service_catalog,
        historical_insights=historical_insights,
    )

    if not ai_result:
        raise HTTPException(status_code=502, detail="AI estimation engine failed to generate estimate")

    canonical = recompute_estimate(ai_result)
    validation_errors = validate_estimate(canonical)
    if validation_errors:
        logger.warning("AI-generated estimate has validation issues: %s", validation_errors)
        canonical["confidence_score"] = 0
        canonical["total"] = 0
        canonical["subtotal"] = 0
        canonical["line_items"] = []
        logger.info("Estimate validation failed — zeroed output for manual review")

    estimate = Estimate(
        company_id=current_user.company_id,
        job_id=req.job_id,
        customer_id=req.customer_id or (job.customer_id if job else None),
        status=EstimateStatus.ai_pending.value,
        title=f"Estimate for: {job_description[:100]}",
        description=job_description,
        subtotal=canonical.get("subtotal", 0),
        tax=_round_currency(float(canonical.get("tax", 0))),
        total=canonical.get("total", 0),
        confidence_score=canonical.get("confidence_score", 50),
        assumptions=canonical.get("assumptions", []),
        ai_generated=True,
    )
    db.add(estimate)
    await db.flush()
    await db.refresh(estimate)

    line_items_data = canonical.get("line_items", [])
    for idx, item in enumerate(line_items_data):
        li = EstimateLineItem(
            estimate_id=estimate.id,
            company_id=current_user.company_id,
            name=item.get("name", ""),
            item_type=item.get("item_type", "labor"),
            quantity=item.get("quantity", 1),
            rate=item.get("rate", 0),
            total=item.get("total", 0),
            sort_order=idx,
            ai_quantity=item.get("quantity", 1),
            ai_rate=item.get("rate", 0),
            ai_total=item.get("total", 0),
        )
        db.add(li)

    await db.flush()

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    snapshot_data = build_estimate_snapshot(estimate, estimate_line_items)
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="ai_generated",
        user_id=current_user.id,
        snapshot_data=snapshot_data,
    )

    await log_event(
        event_name="estimate.created",
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(req.job_id) if req.job_id else None,
        metadata={"estimate_id": str(estimate.id), "total": estimate.total, "confidence": estimate.confidence_score},
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.post("/{estimate_id}/review", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def review_ai_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.status != EstimateStatus.ai_pending.value:
        raise HTTPException(status_code=400, detail=f"Cannot review estimate in status '{estimate.status}'")

    if not estimate.ai_generated:
        raise HTTPException(status_code=400, detail="Only AI-generated estimates require review")

    success = await transition_estimate(db, estimate_id, current_user.company_id, SMStatus.draft)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to transition estimate to draft")

    await db.flush()
    await db.refresh(estimate)

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="human_reviewed",
        user_id=current_user.id,
        snapshot_data=build_estimate_snapshot(estimate, estimate_line_items),
    )

    await log_event(
        event_name="estimate.reviewed",
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(estimate.job_id) if estimate.job_id else None,
        metadata={"estimate_id": str(estimate.id), "total": estimate.total, "ai_generated": estimate.ai_generated},
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.get("", response_model=EstimateListResponse)
async def list_estimates(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = (
        select(Estimate)
        .options(selectinload(Estimate.line_items))
        .where(Estimate.company_id == current_user.company_id)
    )
    if status:
        query = query.where(Estimate.status == status)
    query = query.order_by(Estimate.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    estimates = result.scalars().all()

    count_query = select(func.count(Estimate.id)).where(Estimate.company_id == current_user.company_id)
    if status:
        count_query = count_query.where(Estimate.status == status)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    items = list(estimates)

    return EstimateListResponse(estimates=items, total=total)  # type: ignore[arg-type]


@router.get("/{estimate_id}", response_model=EstimateResponse)
async def get_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _estimate_to_response(db, estimate_id, current_user.company_id)


@router.put("/{estimate_id}", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def update_estimate(
    estimate_id: UUID,
    req: EstimateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.status not in (EstimateStatus.draft.value, EstimateStatus.in_review.value):
        raise HTTPException(status_code=400, detail="Only draft or in-review estimates can be edited")

    if req.title is not None:
        estimate.title = req.title
    if req.description is not None:
        estimate.description = req.description
    if req.notes is not None:
        estimate.notes = req.notes

    if req.line_items is not None:
        line_item_dicts = []
        for _idx, item_data in enumerate(req.line_items):
            canonical_item = recompute_line_item(item_data.model_dump())
            line_item_dicts.append(canonical_item)

        old_items = await db.execute(select(EstimateLineItem).where(EstimateLineItem.estimate_id == estimate.id))
        for item in old_items.scalars().all():
            await db.delete(item)

        for idx, canonical_item in enumerate(line_item_dicts):
            li = EstimateLineItem(
                estimate_id=estimate.id,
                company_id=current_user.company_id,
                name=canonical_item["name"],
                item_type=canonical_item["item_type"],
                quantity=canonical_item["quantity"],
                rate=canonical_item["rate"],
                total=canonical_item["total"],
                sort_order=idx,
                override_reason=req.line_items[idx].override_reason,
            )
            db.add(li)

        computed_subtotal = sum(li["total"] for li in line_item_dicts)
        computed_subtotal = _round_currency(computed_subtotal)
        tax = _round_currency(float(req.tax if req.tax is not None else estimate.tax))
        computed_total = _round_currency(computed_subtotal + tax)
        estimate.subtotal = computed_subtotal
        estimate.tax = tax
        estimate.total = computed_total
    else:
        if req.subtotal is not None:
            estimate.subtotal = req.subtotal
        if req.tax is not None:
            estimate.tax = req.tax
        if req.total is not None:
            estimate.total = req.total

    estimate.ai_generated = False

    await db.flush()

    if estimate.status == EstimateStatus.draft.value:
        estimate.status = EstimateStatus.in_review.value

    await db.flush()

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    current_snapshot_data = build_estimate_snapshot(estimate, estimate_line_items)
    previous_snapshot = await get_latest_snapshot(db, estimate.id, current_user.company_id)
    diff = compute_snapshot_diff(previous_snapshot.snapshot_data, current_snapshot_data) if previous_snapshot else {}
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="edited",
        user_id=current_user.id,
        snapshot_data=current_snapshot_data,
        previous_snapshot_id=previous_snapshot.id if previous_snapshot else None,
        diff_data=diff,
    )

    await log_event(
        event_name="estimate.updated",
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(estimate.job_id) if estimate.job_id else None,
        metadata={"estimate_id": str(estimate.id), "total": estimate.total},
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.post("/{estimate_id}/approve", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def approve_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    success = await transition_estimate(db, estimate_id, current_user.company_id, SMStatus.approved)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot approve estimate in status '{estimate.status}'")

    await db.flush()
    await db.refresh(estimate)

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="approved",
        user_id=current_user.id,
        snapshot_data=build_estimate_snapshot(estimate, estimate_line_items),
    )

    await log_event(
        event_name="estimate.approved",
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(estimate.job_id) if estimate.job_id else None,
        metadata={"estimate_id": str(estimate.id), "total": estimate.total},
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.post("/{estimate_id}/send", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def send_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.status != EstimateStatus.approved.value:
        raise HTTPException(status_code=400, detail="Estimate must be approved before sending")

    success = await transition_estimate(db, estimate_id, current_user.company_id, SMStatus.sent)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to send estimate")

    await db.flush()

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="sent",
        user_id=current_user.id,
        snapshot_data=build_estimate_snapshot(estimate, estimate_line_items),
    )

    await log_event(
        event_name="estimate.sent",
        user_id=current_user.id,
        company_id=str(current_user.company_id),
        job_id=str(estimate.job_id) if estimate.job_id else None,
        metadata={"estimate_id": str(estimate.id), "total": estimate.total},
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.post("/{estimate_id}/reopen", response_model=EstimateResponse, dependencies=[Depends(require_staff)])
async def reopen_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.status not in (EstimateStatus.sent.value, EstimateStatus.rejected.value):
        raise HTTPException(status_code=400, detail="Only sent or rejected estimates can be reopened")

    estimate.status = EstimateStatus.in_review.value
    await db.flush()

    line_items_result = await db.execute(
        select(EstimateLineItem)
        .where(EstimateLineItem.estimate_id == estimate.id)
        .order_by(EstimateLineItem.sort_order)
    )
    estimate_line_items = list(line_items_result.scalars().all())
    await record_snapshot(
        db=db,
        estimate_id=estimate.id,
        company_id=current_user.company_id,
        event_type="reopened",
        user_id=current_user.id,
        snapshot_data=build_estimate_snapshot(estimate, estimate_line_items),
    )

    return await _estimate_to_response(db, estimate.id, current_user.company_id)


@router.delete("/{estimate_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_estimate(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id, Estimate.company_id == current_user.company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    await db.delete(estimate)
    await db.flush()
    return None


@router.get("/brain/me", response_model=CompanyPricingBrainResponse)
async def get_company_pricing_brain(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CompanyPricingBrain).where(CompanyPricingBrain.company_id == current_user.company_id)
    )
    brain = result.scalar_one_or_none()
    if not brain:
        raise HTTPException(status_code=404, detail="Company pricing brain not configured")
    return brain


@router.put("/brain/me", response_model=CompanyPricingBrainResponse, dependencies=[Depends(require_admin)])
async def update_company_pricing_brain(
    data: CompanyPricingBrainUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CompanyPricingBrain).where(CompanyPricingBrain.company_id == current_user.company_id)
    )
    brain = result.scalar_one_or_none()
    if not brain:
        brain = CompanyPricingBrain(company_id=current_user.company_id)
        db.add(brain)

    import copy

    before = {c.key: copy.deepcopy(getattr(brain, c.key)) for c in brain.__table__.columns}

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(brain, key, value)

    after = {c.key: copy.deepcopy(getattr(brain, c.key)) for c in brain.__table__.columns}
    changes = {k: {"from": before.get(k), "to": after.get(k)} for k in update_data if before.get(k) != after.get(k)}

    await db.flush()
    await db.refresh(brain)

    if changes:
        logger.info("Pricing brain updated by user %s: %s", current_user.id, changes)
        await log_event(
            event_name="pricing_brain_updated",
            user_id=current_user.id,
            company_id=str(current_user.company_id),
            metadata={"changes": changes},
        )

    return brain


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.company_id == current_user.company_id))
    services = result.scalars().all()
    return services


@router.post("/services", response_model=ServiceResponse, dependencies=[Depends(require_admin)])
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = Service(
        company_id=current_user.company_id,
        name=data.name,
        avg_time_hours=data.avg_time_hours,
        pricing_type=data.pricing_type,
        flat_rate=data.flat_rate,
        material_assumptions=data.material_assumptions,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Service).where(Service.id == service_id, Service.company_id == current_user.company_id)
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.delete(service)
    await db.flush()
    return None


@router.post("/historical", response_model=dict)
async def record_historical_job(
    data: HistoricalJobRecord,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = HistoricalJobData(
        company_id=current_user.company_id,
        service_type=data.service_type,
        estimated_hours=data.estimated_hours,
        actual_hours=data.actual_hours,
        estimated_cost=data.estimated_cost,
        actual_cost=data.actual_cost,
        materials_used=data.materials_used,
        final_invoice_amount=data.final_invoice_amount,
        technician_notes=data.technician_notes,
        job_completed_at=datetime.now(UTC),
    )
    db.add(record)
    await db.flush()
    return {"status": "recorded", "id": str(record.id)}


@router.get("/historical/summary", response_model=dict)
async def get_historical_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(
            HistoricalJobData.service_type,
            func.avg(HistoricalJobData.actual_hours).label("avg_hours"),
            func.avg(HistoricalJobData.actual_cost).label("avg_cost"),
            func.count(HistoricalJobData.id).label("count"),
            func.avg(HistoricalJobData.estimated_hours).label("avg_estimated_hours"),
        )
        .where(HistoricalJobData.company_id == current_user.company_id)
        .group_by(HistoricalJobData.service_type)
        .order_by(func.count(HistoricalJobData.id).desc())
    )
    rows = result.all()

    return {
        "insights": [
            {
                "service_type": row.service_type,
                "avg_hours": round(row.avg_hours, 2) if row.avg_hours else 0,
                "avg_cost": round(row.avg_cost, 2) if row.avg_cost else 0,
                "count": row.count,
                "avg_estimated_hours": round(row.avg_estimated_hours, 2) if row.avg_estimated_hours else 0,
            }
            for row in rows
        ]
    }


@router.get("/{estimate_id}/audit", response_model=dict)
async def get_estimate_audit_trail(
    estimate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshots = await get_snapshots(db, estimate_id, current_user.company_id)
    return {
        "estimate_id": str(estimate_id),
        "snapshots": [
            {
                "id": str(s.id),
                "event_type": s.event_type,
                "user_id": s.user_id,
                "snapshot_data": s.snapshot_data,
                "diff_data": s.diff_data,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ],
        "total": len(snapshots),
    }


async def _estimate_to_response(
    db: AsyncSession,
    estimate_id: UUID,
    company_id: UUID,
) -> EstimateResponse:

    result = await db.execute(
        select(Estimate)
        .options(selectinload(Estimate.line_items))
        .where(Estimate.id == estimate_id, Estimate.company_id == company_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return estimate  # type: ignore[return-value]
