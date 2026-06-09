#!/usr/bin/env python3
"""H-5 verification: Verify per-queue backpressure thresholds.

Checks:
- Each queue has its own threshold
- Thresholds are reasonable
- Per-queue check replaces total queue depth check
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.h5")

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

async def test_per_queue_thresholds():
    """Verify per-queue thresholds exist with correct values."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "H-5: Per-queue backpressure comment",
        "H-5" in content and "Per-queue backpressure" in content
    )
    check(
        "_queue_thresholds dict defined",
        "_queue_thresholds" in content
    )
    check(
        "default queue threshold 500",
        '"default": 500' in content
    )
    check(
        "ai_text queue threshold 200",
        '"ai_text": 200' in content
    )
    check(
        "ai_audio queue threshold 200",
        '"ai_audio": 200' in content
    )
    check(
        "ai_image queue threshold 200",
        '"ai_image": 200' in content
    )
    check(
        "beat queue threshold 50",
        '"beat": 50' in content
    )

async def test_loop_checks_each_queue():
    """Verify the code iterates over each queue individually."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "Iterates over _queue_thresholds dict",
        "for q in _queue_thresholds:" in content
    )
    check(
        "Checks individual queue depth",
        "depth = _bp_redis.llen(q) or 0" in content
    )
    check(
        "Individual error message per queue",
        "Queue {q} depth too high" in content
    )

async def test_old_total_depth_removed():
    """Verify old total-depth approach was replaced."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    section = content[content.find("def enqueue_job_task"):content.find("def enqueue_job_task") + 2000]
    check(
        "Old _total_depth calculation removed",
        "_total_depth" not in section
    )

def main():
    asyncio.run(test_per_queue_thresholds())
    asyncio.run(test_loop_checks_each_queue())
    asyncio.run(test_old_total_depth_removed())

    total = PASSED + FAILED
    logger.info("H-5 Results: %d/%d passed", PASSED, total)
    result = {"test": "H-5 Per-Queue Backpressure", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
