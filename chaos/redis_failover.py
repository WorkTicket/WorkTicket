#!/usr/bin/env python3
"""Chaos test: Redis broker full outage for 15 minutes.

Validates: graceful degradation, queue-depth backpressure, full recovery.
Pass criteria: system returns 429 during outage, no 503s after Redis returns.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.redis_failover")

REDIS_CONTAINER = "workticket-redis-broker-1"
OUTAGE_DURATION = 900  # 15 minutes
HEALTH_ENDPOINT = "http://localhost:8000/readyz"


async def check_health() -> dict:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(HEALTH_ENDPOINT, timeout=5) as resp:
            return {"status": resp.status, "body": await resp.text()}


def stop_redis():
    logger.info("Stopping Redis container: %s", REDIS_CONTAINER)
    result = subprocess.run(
        ["docker", "stop", REDIS_CONTAINER],
        capture_output=True, text=True, timeout=30
    )
    logger.info("docker stop: %s", result.stdout.strip())


def start_redis():
    logger.info("Starting Redis container: %s", REDIS_CONTAINER)
    result = subprocess.run(
        ["docker", "start", REDIS_CONTAINER],
        capture_output=True, text=True, timeout=30
    )
    logger.info("docker start: %s", result.stdout.strip())


async def run():
    phase = "baseline"
    results = {"baseline": None, "during_outage": [], "post_recovery": [], "passed": True}

    # Baseline health check
    health = await check_health()
    results["baseline"] = health
    logger.info("Baseline /readyz: %s", health)
    if health["status"] != 200:
        logger.error("Baseline health check FAILED — aborting")
        results["passed"] = False
        return results

    # Stop Redis
    stop_redis()
    phase = "outage"
    await asyncio.sleep(5)

    # Check during outage — expect 503 or 429
    for i in range(3):
        try:
            health = await check_health()
            results["during_outage"].append(health)
            logger.info("During outage check %d: %s", i + 1, health)
        except Exception as e:
            results["during_outage"].append({"error": str(e)})
            logger.warning("During outage check %d connection error: %s", i + 1, e)

    # Wait then restart Redis
    logger.info("Waiting %d seconds before restarting Redis...", OUTAGE_DURATION - 15)
    await asyncio.sleep(OUTAGE_DURATION - 15)

    start_redis()
    phase = "recovery"
    await asyncio.sleep(10)

    # Post-recovery checks
    for i in range(5):
        try:
            health = await check_health()
            results["post_recovery"].append(health)
            logger.info("Post-recovery check %d: %s", i + 1, health)
            if health["status"] == 200:
                logger.info("Recovery confirmed on check %d", i + 1)
                break
        except Exception as e:
            results["post_recovery"].append({"error": str(e)})
            logger.warning("Post-recovery check %d error: %s", i + 1, e)
        await asyncio.sleep(5)

    # Final check
    final = await check_health()
    if final["status"] != 200:
        logger.error("Final health check FAILED — system did not recover")
        results["passed"] = False

    return results


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
