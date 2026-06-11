import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.cost_estimator import ACU_TO_USD
from app.billing.models import BillingAccount, UsageLedger

logger = logging.getLogger(__name__)


async def _check_duplicate_credit(
    db: AsyncSession,
    company_id: UUID,
    job_id: UUID,
    reason: str,
) -> bool:
    existing = await db.execute(
        select(UsageLedger).where(
            UsageLedger.company_id == company_id,
            UsageLedger.job_id == job_id,
            UsageLedger.is_credit.is_(True),
            UsageLedger.credit_reason == reason,
        )
    )
    return existing.scalar_one_or_none() is not None


async def grant_credit(
    db: AsyncSession,
    company_id: UUID,
    job_id: UUID,
    amount_acu: float,
    reason: str,
    granted_by: str | None = None,
) -> dict:
    result = await db.execute(select(BillingAccount).where(BillingAccount.company_id == company_id).with_for_update())
    account = result.scalar_one_or_none()

    # Check duplicate INSIDE the FOR UPDATE lock to prevent double-credit race
    if account and await _check_duplicate_credit(db, company_id, job_id, reason):
        logger.info("Duplicate credit for job %s (reason: %s) — skipping", job_id, reason)
        return {"status": "skipped_duplicate", "company_id": str(company_id), "job_id": str(job_id)}
    if not account:
        return {"status": "no_account", "company_id": str(company_id)}

    credit_cost_usd = Decimal(str(amount_acu)) * Decimal(str(ACU_TO_USD))

    account.used_acu -= Decimal(str(amount_acu))
    if account.used_acu < Decimal("0"):
        account.used_acu = Decimal("0")

    billing_period = (
        account.billing_period_start.strftime("%Y-%m")
        if account.billing_period_start
        else datetime.now(UTC).strftime("%Y-%m")
    )

    # Use pg_insert with on_conflict_do_nothing for DB-level dedup (L5)
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    insert_stmt = (
        pg_insert(UsageLedger)
        .values(
            company_id=company_id,
            job_id=job_id,
            text_units=0,
            vision_units=0,
            audio_units=0,
            cost_usd=-credit_cost_usd,
            estimated_cost_usd=Decimal("0"),
            model_used="credit",
            execution_time_ms=0,
            billing_period=billing_period,
            is_credit=True,
            credit_reason=reason[:255],
            original_job_id=job_id,
        )
        .on_conflict_do_nothing(
            index_elements=["job_id", "company_id"],
            index_where=UsageLedger.job_id.isnot(None),
        )
    )
    credit_result = await db.execute(insert_stmt)
    if credit_result.rowcount == 0:  # type: ignore[attr-defined]
        logger.info("Duplicate credit for job %s (reason: %s) caught by DB constraint — skipping", job_id, reason)
        return {"status": "skipped_duplicate", "company_id": str(company_id), "job_id": str(job_id)}

    logger.info(
        "Credit granted to company %s for job %s: %.4f ACU (reason: %s) by %s",
        company_id,
        job_id,
        amount_acu,
        reason,
        granted_by or "system",
    )

    return {
        "status": "credited",
        "company_id": str(company_id),
        "job_id": str(job_id),
        "amount_acu": amount_acu,
        "reason": reason,
        "used_acu_after": float(account.used_acu),
    }


async def auto_credit_failed_job(
    db: AsyncSession,
    company_id: UUID,
    job_id: UUID,
    reserved_acu: float,
) -> dict:
    if reserved_acu <= 0:
        return {"status": "no_reservation"}

    return await grant_credit(
        db=db,
        company_id=company_id,
        job_id=job_id,
        amount_acu=reserved_acu,
        reason="auto_credit: job processing failed",
        granted_by="system",
    )
