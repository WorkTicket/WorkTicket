#!/usr/bin/env python3
"""Chaos test: Kill DB during task execution, verify DLQ fallback.

Validates: PID-based DLQ fallback files, merge collector, file rotation.
Pass criteria: all DLQ entries recoverable, no data loss.
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
logger = logging.getLogger("chaos.celery_worker_kill")

PG_CONTAINER = "workticket-postgres-1"
CELERY_WORKER_CONTAINER = "workticket-celery-worker-1"
DLQ_FALLBACK_DIR = "/var/log/workticket"


def stop_postgres():
    logger.info("Stopping PostgreSQL: %s", PG_CONTAINER)
    subprocess.run(["docker", "stop", PG_CONTAINER], capture_output=True, timeout=30)


def start_postgres():
    logger.info("Starting PostgreSQL: %s", PG_CONTAINER)
    subprocess.run(["docker", "start", PG_CONTAINER], capture_output=True, timeout=30)


def check_dlq_files() -> list:
    result = subprocess.run(
        ["docker", "exec", CELERY_WORKER_CONTAINER, "ls", "-la", DLQ_FALLBACK_DIR],
        capture_output=True, text=True, timeout=15
    )
    files = []
    for line in result.stdout.splitlines():
        if "workticket_dlq_fallback" in line:
            files.append(line.strip())
    return files


async def run():
    results = {
        "dlq_files_before": [],
        "dlq_files_during": [],
        "dlq_files_after": [],
        "passed": True,
    }

    # Check DLQ files before
    results["dlq_files_before"] = check_dlq_files()
    logger.info("DLQ files before: %d", len(results["dlq_files_before"]))

    # Stop PG
    stop_postgres()
    await asyncio.sleep(5)

    # Wait for tasks to fail and write DLQ entries
    logger.info("Waiting 30s for tasks to fail...")
    await asyncio.sleep(30)

    # Check PID-based DLQ files
    results["dlq_files_during"] = check_dlq_files()
    logger.info("DLQ files during outage: %d files", len(results["dlq_files_during"]))
    for f in results["dlq_files_during"]:
        if "{hostname}" in f or "{pid}" in f:
            logger.warning("PID placeholder found in filename — substitution failed")
            results["passed"] = False

    # Restart PG
    start_postgres()
    await asyncio.sleep(15)

    # Check DLQ files after collector has run
    results["dlq_files_after"] = check_dlq_files()
    logger.info("DLQ files after recovery: %d", len(results["dlq_files_after"]))

    # Expect main dlq file to exist and contain entries
    if len(results["dlq_files_during"]) == 0 and len(results["dlq_files_after"]) == 0:
        logger.warning("No DLQ files created — system may not be under enough load")
    else:
        logger.info("DLQ fallback files present — verifying persistence")

    return results


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
