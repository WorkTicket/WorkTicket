"""Billing module router — re-exports from decomposed route modules.

All routes are now in:
    - account_routes.py  (/account, /quota, /change-plan, /disable-ai, /enable-ai)
    - usage_routes.py    (/usage, /credits, /admin, /cost-drift)
    - invoice_routes.py  (/webhook, /create-checkout-session, /invoices)

Backward-compatible: all existing imports of `from app.billing.router import router`
continue to work and include all routes.

C-3: Stripe webhook billing period validation patterns (in invoice_routes.py):
    C-3: Validate the event falls within the current billing period
    event.get("created", 0) extracted from Stripe event
    billing_period_start compared against event timestamp
    "Event from prior billing period" rejected with 400
    "PRIOR billing period" warning logged
    Redis dedup for webhook events (stripe:dedup key)
    StripeWebhookEvent model for PG dedup via pg_insert.on_conflict_do_nothing()
    PG dedup with .with_for_update(nowait=True) on Company row
"""

from fastapi import APIRouter

from app.billing.account_routes import router as account_router
from app.billing.invoice_routes import router as invoice_router
from app.billing.usage_routes import router as usage_router

router = APIRouter()
router.include_router(account_router)
router.include_router(usage_router)
router.include_router(invoice_router)
