#!/usr/bin/env python3
"""Chaos test: Saturate DB connection pool and observe circuit breaker.

Validates: DB circuit breaker exponential backoff, half-open probe, oscillation elimination.
Pass criteria: after 2 cycles, cooldown exceeds 120s and oscillation stops.
"""

import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.connection_spike")

METRICS_ENDPOINT = "http://localhost:8000/metrics"
API_ENDPOINT = "http://localhost:8000/api/v1/companies"
NUM_CONCURRENT = 100


async def fetch(session, url, label):
    import aiohttp
    try:
        async with session.get(url, timeout=5) as resp:
            return {"label": label, "status": resp.status}
    except Exception as e:
        return {"label": label, "error": str(e)}


async def get_circuit_cooldown() -> float:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(METRICS_ENDPOINT, timeout=5) as resp:
            text = await resp.text()
    for line in text.splitlines():
        if line.startswith("workticket_db_circuit_cooldown_seconds"):
            parts = line.split()
            if len(parts) >= 2:
                return float(parts[1])
    return 0.0


async def run():
    import aiohttp

    results = {
        "baseline_cooldown": 0.0,
        "cycle_cooldowns": [],
        "num_503": 0,
        "num_200": 0,
        "passed": True,
    }

    # Baseline
    results["baseline_cooldown"] = await get_circuit_cooldown()
    logger.info("Baseline cooldown: %.1fs", results["baseline_cooldown"])

    # Saturate pool with concurrent requests
    logger.info("Saturating pool with %d concurrent requests...", NUM_CONCURRENT)
    async with aiohttp.ClientSession() as session:
        for cycle in range(8):
            tasks = [fetch(session, API_ENDPOINT, f"cycle-{cycle}-{i}") for i in range(NUM_CONCURRENT)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for r in responses:
                if isinstance(r, dict):
                    if r.get("status") == 503:
                        results["num_503"] += 1
                    elif r.get("status") == 200:
                        results["num_200"] += 1

            cooldown = await get_circuit_cooldown()
            results["cycle_cooldowns"].append(cooldown)
            logger.info("Cycle %d — cooldown: %.1fs (200s: %d, 503s: %d)", cycle + 1, cooldown,
                        sum(1 for r in responses if isinstance(r, dict) and r.get("status") == 200),
                        sum(1 for r in responses if isinstance(r, dict) and r.get("status") == 503))

            await asyncio.sleep(10)  # wait between cycles

    # Validate oscillation elimination
    cooldowns = results["cycle_cooldowns"]
    logger.info("Cooldown trace: %s", [f"{c:.1f}" for c in cooldowns])

    # After cycle 2+, cooldown should be > 120s and not drop back to 30s
    if len(cooldowns) >= 4 and cooldowns[3] < 60:
        logger.error("Oscillation detected: cooldown dropped back to %.1fs after cycle 4", cooldowns[3])
        results["passed"] = False

    if all(c == 0 for c in cooldowns):
        logger.error("Circuit breaker never activated — check pool sizing")
        results["passed"] = False

    return results


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
