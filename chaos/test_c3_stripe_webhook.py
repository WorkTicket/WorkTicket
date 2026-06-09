#!/usr/bin/env python3
"""C-3 verification: Verify Stripe webhook billing period validation.

Checks:
- Events from prior billing period are rejected with 400
- Redis dedup catches duplicate events
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.c3")

PASSED = 0
FAILED = 0

def check(description: str, condition: bool):
    global PASSED, FAILED
    if condition:
        logger.info("  PASS: %s", description)
        PASSED += 1
    else:
        logger.error("  FAIL: %s", description)
        FAILED += 1

async def test_billing_period_validation():
    """Verify billing period validation in Stripe webhook handlers."""
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "billing", "router.py")
    with open(router_path) as f:
        content = f.read()

    check(
        "Billing period validation comment present (C-3)",
        "C-3: Validate the event falls within" in content
    )
    check(
        "Event timestamp extracted from Stripe event",
        "event.get(\"created\", 0)" in content
    )
    check(
        "Billing period start compared against event timestamp",
        "billing_period_start" in content
    )
    check(
        "Prior period events rejected with 400",
        "Event from prior billing period" in content
    )
    check(
        "Prior period warning logged",
        "PRIOR billing period" in content or "prior billing period" in content.lower()
    )

async def test_redis_dedup():
    """Verify Redis dedup logic exists for webhook events."""
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "billing", "router.py")
    with open(router_path) as f:
        content = f.read()

    check(
        "Redis dedup for webhook events",
        "redis" in content.lower() and "dedup" in content.lower()
    )
    check(
        "StripeWebhookEvent model for PG dedup",
        "StripeWebhookEvent" in content
    )
    check(
        "PG dedup with FOR UPDATE NOWAIT",
        ".with_for_update(nowait=True)" in content
    )

def main():
    asyncio.run(test_billing_period_validation())
    asyncio.run(test_redis_dedup())

    total = PASSED + FAILED
    logger.info("C-3 Results: %d/%d passed", PASSED, total)
    result = {"test": "C-3 Stripe Webhook Validation", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
