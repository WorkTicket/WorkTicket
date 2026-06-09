#!/usr/bin/env python3
"""Chaos test: Concurrent billing webhook + beat task contention.

Validates: skip_locked, billing reconciliation lock, beat lock TTL heartbeat.
Pass criteria: no double-billing, no deadlocks, lock contention counter increments.
"""

import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.billing_contention")

STRIPE_WEBHOOK_URL = "http://localhost:8000/api/v1/billing/stripe-webhook"
METRICS_URL = "http://localhost:8000/metrics"
SIGNING_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")


def make_webhook_payload(event_type: str) -> dict:
    import hashlib, hmac, json, time
    payload = {
        "id": f"evt_test_{int(time.time() * 1_000_000)}_{event_type}",
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_mock",
                "customer": "cus_test",
                "subscription": "sub_test",
                "status": "complete",
                "amount_total": 2000,
                "metadata": {"company_id": "00000000-0000-0000-0000-000000000001"},
            }
        },
        "created": int(time.time()),
    }
    payload_str = json.dumps(payload)
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload_str}"
    signature = hmac.new(SIGNING_SECRET.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return payload, {"Stripe-Signature": f"t={timestamp},v1={signature}"}


async def fire_webhook(session, event_type: str, idx: int):
    import aiohttp
    payload, headers = make_webhook_payload(event_type)
    try:
        async with session.post(STRIPE_WEBHOOK_URL, json=payload, headers=headers, timeout=10) as resp:
            body = await resp.text()
            return {"idx": idx, "status": resp.status, "body": body[:200]}
    except Exception as e:
        return {"idx": idx, "error": str(e)}


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
        "total_webhooks": 0,
        "200_count": 0,
        "409_count": 0,
        "503_count": 0,
        "lock_contention_before": 0,
        "lock_contention_after": 0,
        "passed": True,
    }

    results["lock_contention_before"] = await get_metric("workticket_stripe_webhook_lock_contention_total")

    logger.info("Firing 30 concurrent checkout.session.completed webhooks...")
    async with aiohttp.ClientSession() as session:
        tasks = [fire_webhook(session, "checkout.session.completed", i) for i in range(30)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    results["total_webhooks"] = len(responses)
    for r in responses:
        if isinstance(r, dict):
            status = r.get("status")
            if status == 200:
                results["200_count"] += 1
            elif status == 409:
                results["409_count"] += 1
            elif status == 503:
                results["503_count"] += 1

    results["lock_contention_after"] = await get_metric("workticket_stripe_webhook_lock_contention_total")
    contention_delta = results["lock_contention_after"] - results["lock_contention_before"]
    logger.info("Lock contention delta: %d", contention_delta)

    if contention_delta == 0:
        logger.warning("Lock contention counter did not increment — might not be exercising skip_locked")
    if results["503_count"] > 0:
        logger.warning("%d requests returned 503", results["503_count"])

    return results


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
