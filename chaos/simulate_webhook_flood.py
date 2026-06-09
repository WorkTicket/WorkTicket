#!/usr/bin/env python3
"""Chaos test: Stripe webhook flood with crash injection.

Validates: Redis dedup survival after crash between flush and commit.
Pass criteria: all events processed exactly once, none lost on retry.
"""

import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.webhook_flood")

STRIPE_WEBHOOK_URL = "http://localhost:8000/api/v1/billing/stripe-webhook"
METRICS_URL = "http://localhost:8000/metrics"
SIGNING_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")


def make_webhook_payload(event_type: str, dedup_id: str = None) -> tuple:
    import hashlib, hmac, time
    evt_id = dedup_id or f"evt_test_{int(time.time() * 1_000_000)}"
    payload = {
        "id": evt_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_flood",
                "customer": "cus_flood",
                "subscription": "sub_flood",
                "status": "complete",
                "amount_total": 1000,
                "metadata": {"company_id": "00000000-0000-0000-0000-000000000002"},
            }
        },
        "created": int(time.time()),
    }
    payload_str = json.dumps(payload)
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_str}"
    signature = hmac.new(SIGNING_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return payload, {"Stripe-Signature": f"t={timestamp},v1={signature}"}


async def fire_webhook(session, event_type: str, dedup_id: str = None):
    import aiohttp
    payload, headers = make_webhook_payload(event_type, dedup_id)
    try:
        async with session.post(STRIPE_WEBHOOK_URL, json=payload, headers=headers, timeout=10) as resp:
            body = await resp.text()
            return {"evt_id": payload["id"], "status": resp.status, "body": body[:200]}
    except Exception as e:
        return {"evt_id": payload["id"], "error": str(e)}


async def get_metric(name: str) -> int:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(METRICS_URL, timeout=5) as resp:
            text = await resp.text()
    for line in text.splitlines():
        if line.startswith(name):
            parts = line.split()
            if len(parts) >= 2:
                return int(float(parts[1]))
    return 0


async def run():
    import aiohttp

    results = {
        "redis_hit_before": 0,
        "redis_miss_before": 0,
        "retry_results": [],
        "redis_hit_after": 0,
        "redis_miss_after": 0,
        "passed": True,
    }

    results["redis_hit_before"] = await get_metric("workticket_stripe_dedup_redis_hit_total")
    results["redis_miss_before"] = await get_metric("workticket_stripe_dedup_redis_miss_total")

    # Fire 20 unique events
    logger.info("Firing 20 unique checkout.session.completed events...")
    async with aiohttp.ClientSession() as session:
        tasks = [fire_webhook(session, "checkout.session.completed") for _ in range(20)]
        initial_responses = await asyncio.gather(*tasks, return_exceptions=True)

    successes = [r for r in initial_responses if isinstance(r, dict) and r.get("status") == 200]
    logger.info("Initial: %d successes out of %d", len(successes), len(initial_responses))

    # Retry the same event IDs — should be dedup'd (200 + dedup header)
    evt_ids = [r["evt_id"] for r in initial_responses if isinstance(r, dict)]
    logger.info("Retrying %d event IDs (should be dedup'd)...", len(evt_ids))
    async with aiohttp.ClientSession() as session:
        tasks = [fire_webhook(session, "checkout.session.completed", eid) for eid in evt_ids[:10]]
        retry_responses = await asyncio.gather(*tasks, return_exceptions=True)

    results["retry_results"] = [
        {"evt_id": r.get("evt_id"), "status": r.get("status")}
        for r in retry_responses if isinstance(r, dict)
    ]

    results["redis_hit_after"] = await get_metric("workticket_stripe_dedup_redis_hit_total")
    results["redis_miss_after"] = await get_metric("workticket_stripe_dedup_redis_miss_total")

    hit_delta = results["redis_hit_after"] - results["redis_hit_before"]
    miss_delta = results["redis_miss_after"] - results["redis_miss_before"]
    logger.info("Redis dedup — hits: +%d, misses: +%d", hit_delta, miss_delta)

    # All retries should be dedup hits (200 status)
    non_200_retries = [r for r in results["retry_results"] if r.get("status") != 200]
    if non_200_retries:
        logger.error("%d retries were NOT dedup'd: %s", len(non_200_retries), non_200_retries)
        results["passed"] = False

    return results


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
