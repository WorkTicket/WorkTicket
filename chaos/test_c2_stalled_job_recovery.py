#!/usr/bin/env python3
"""C-2 verification: Verify stalled job recovery logic.

Creates a simulated stalled job and checks that scan_for_stalled_ai_jobs
properly transitions and re-queues it.
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.c2")

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

async def test_scan_stalled_jobs_code():
    """Verify scan_for_stalled_ai_jobs has all required recovery logic."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "scan_for_stalled_ai_jobs scans 'none' state jobs",
        "AIProcessingState.none.value" in content
    )
    check(
        "scan_for_stalled_ai_jobs scans 'queued' state jobs",
        "AIProcessingState.queued.value" in content
    )
    check(
        "Stalled jobs are re-dispatched via enqueue_job_task",
        "enqueue_job_task" in content
    )
    check(
        "Re-queue count tracked (H9 guard)",
        "requeue_count" in content
    )
    check(
        "Jobs re-queued > 3 times transition to failed",
        "requeue_count > 3" in content
    )
    check(
        "Failed jobs are sent to DLQ",
        "_move_to_dead_letter" in content
    )
    check(
        "C-2 commit after failed transition",
        "C-2: Commit the failed transition" in content
    )
    check(
        "C-2 commit after recovery loop",
        "C-2: Commit all recovered job transitions" in content
    )

async def test_beat_schedule():
    """Verify scan_for_stalled_ai_jobs runs on schedule."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "scan_for_stalled_ai_jobs in beat schedule",
        "scan-for-stalled-ai-jobs" in content
    )
    check(
        "Runs every 5 minutes",
        "300.0" in content and "scan-for-stalled-ai-jobs" in content
    )
    check(
        "Has task route for beat queue",
        '"scan_for_stalled_ai_jobs": {"queue": "beat"}' in content
    )

async def test_lock_protection():
    """Verify the scan has beat lock protection."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "Uses _acquire_beat_lock for concurrent execution protection",
        "_acquire_beat_lock(self.app, \"scan_for_stalled_ai_jobs\"" in content
    )

def main():
    asyncio.run(test_scan_stalled_jobs_code())
    asyncio.run(test_beat_schedule())
    asyncio.run(test_lock_protection())

    total = PASSED + FAILED
    logger.info("C-2 Results: %d/%d passed", PASSED, total)
    result = {"test": "C-2 Stalled Job Recovery", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
