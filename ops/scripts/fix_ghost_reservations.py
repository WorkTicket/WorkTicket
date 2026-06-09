"""One-time script to detect and fix leaked (ghost) reservations.

Ghost reservations occur when:
1. API handler reserves quota but enqueue fails, and the except handler
   doesn't release the reservation (pre-V2-FIX behavior)
2. Celery task crashes before release_reserved runs
3. Celery task retries accumulate multiple reservations

Usage:
    python ops/scripts/fix_ghost_reservations.py

This script is idempotent and safe to run multiple times.
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_ghost_reservations")


async def fix_ghost_reservations():
    """Detect billing accounts where reserved_acu exceeds expected based on in-flight jobs."""
    from app.database import AsyncSessionLocal
    from app.billing.models import BillingAccount
    from app.jobs.models import Job
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BillingAccount).where(BillingAccount.reserved_acu > Decimal("0"))
        )
        accounts = result.scalars().all()
        total_fixed = 0
        total_excess = Decimal("0")

        for account in accounts:
            jobs_result = await db.execute(
                select(Job).where(
                    Job.company_id == account.company_id,
                    Job.ai_processing_state.in_(["queued", "reserved", "processing"]),
                )
            )
            active_jobs = jobs_result.scalars().all()
            expected_reserved = Decimal(str(len(active_jobs))) * Decimal("0.01")

            if account.reserved_acu > expected_reserved * Decimal("1.5"):
                excess = account.reserved_acu - expected_reserved
                logger.critical(
                    "Ghost reservation: company=%s reserved=%.4f expected=%.4f excess=%.4f",
                    account.company_id, float(account.reserved_acu),
                    float(expected_reserved), float(excess),
                )
                account.reserved_acu = expected_reserved
                account.acu_debt = account.acu_debt + Decimal(
                    str(max(0, float(excess) * Decimal("0.1")))
                )
                total_fixed += 1
                total_excess += excess
            elif account.reserved_acu > expected_reserved:
                logger.info(
                    "Minor over-reservation: company=%s reserved=%.4f expected=%.4f "
                    "(within 50%% tolerance — not auto-fixing)",
                    account.company_id, float(account.reserved_acu), float(expected_reserved),
                )

        if total_fixed:
            await db.commit()
            logger.info(
                "Fixed %d accounts with ghost reservations, released %.4f total excess ACU",
                total_fixed, float(total_excess),
            )
        else:
            logger.info("No ghost reservations found — all accounts healthy")

        return {"fixed": total_fixed, "excess_acu": float(total_excess)}


def main():
    result = asyncio.run(fix_ghost_reservations())
    print(f"Fixed {result['fixed']} accounts, released {result['excess_acu']:.4f} excess ACU")


if __name__ == "__main__":
    main()
