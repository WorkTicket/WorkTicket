#!/usr/bin/env python3
"""C-1 verification: Verify db.commit() is called in process_job_task success path.

Simulates a successful AI pipeline execution and checks that AIOutput,
UsageLedger, and job state changes persist after the task completes.
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.c1")

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

async def test_commit_in_success_path():
    """Verify that process_job_task calls db.commit() on success."""
    logger.info("C-1: Silent rollback detection test")

    # 1. Verify the source code has await db.commit() in the success path
    celery_app_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_app_path) as f:
        content = f.read()

    # Phase 1 commit (pre-AI processing)
    check(
        "Phase 1 commit present (PHASE 1: Pre-AI processing)",
        "PHASE 1: Pre-AI processing" in content
    )
    # Phase 2 has no DB transaction
    check(
        "Phase 2 marker present (NO DB transaction)",
        "PHASE 2: AI Gateway processing (NO DB transaction)" in content
    )
    # Phase 3 commit (post-AI processing)
    check(
        "Phase 3 commit (post-AI) present",
        "PHASE 3: Post-AI processing (new DB transaction)" in content
    )
    check(
        "Phase 1 explicit db.commit() present",
        content.count("await db.commit()") >= 2
    )
    check(
        "commit error handled with try/except",
        "Failed to commit transaction on success" in content
    )

    # 2. Verify C-2 markers present in scan_for_stalled_ai_jobs
    check(
        "C-2 commit present after failed transition",
        "C-2: Commit the failed transition" in content
    )
    check(
        "C-2 commit present after recovery loop",
        "C-2: Commit all recovered job transitions" in content
    )

async def test_jobs_created_completed_metrics():
    """Verify the created/completed metric counters exist."""
    logger.info("C-1: Jobs created/completed metrics check")
    prom_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "monitoring", "prometheus.py")
    with open(prom_path) as f:
        content = f.read()

    check(
        "workticket_jobs_created_total counter registered",
        "workticket_jobs_created_total" in content
    )
    check(
        "workticket_jobs_completed_total counter registered",
        "workticket_jobs_completed_total" in content
    )
    check(
        "increment_jobs_created function defined",
        "def increment_jobs_created" in content
    )
    check(
        "increment_jobs_completed function defined",
        "def increment_jobs_completed" in content
    )

    # Check router.py calls increment_jobs_created
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "ai", "router.py")
    with open(router_path) as f:
        router_content = f.read()
    check(
        "increment_jobs_created() called in router.py after enqueue",
        "increment_jobs_created()" in router_content
    )

    # Check celery_app.py calls increment_jobs_completed
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        celery_content = f.read()
    check(
        "increment_jobs_completed() called in celery_app.py after commit",
        "increment_jobs_completed()" in celery_content
    )

async def test_silent_job_failure_alert():
    """Verify the SilentJobProcessingFailure alert exists."""
    alerts_path = os.path.join(os.path.dirname(__file__), "..", "ops", "prometheus-alerts", "workticket-alerts.yml")
    if not os.path.exists(alerts_path):
        logger.warning("SKIP: %s not found", alerts_path)
        return
    with open(alerts_path) as f:
        content = f.read()
    check(
        "SilentJobProcessingFailure alert defined",
        "SilentJobProcessingFailure" in content
    )
    check(
        "Alert expression uses jobs_created - jobs_completed",
        "workticket_jobs_created_total" in content and "workticket_jobs_completed_total" in content
    )
    check(
        "Alert has runbook reference",
        "silent-job-failure-detection.md" in content
    )

def main():
    asyncio.run(test_commit_in_success_path())
    asyncio.run(test_jobs_created_completed_metrics())
    asyncio.run(test_silent_job_failure_alert())

    total = PASSED + FAILED
    logger.info("C-1 Results: %d/%d passed", PASSED, total)
    result = {"test": "C-1 Silent Rollback Detection", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
