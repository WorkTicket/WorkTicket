#!/usr/bin/env python3
"""C-5 verification: Verify event loop isolation with new_event_loop pattern.

Checks:
- Per-task event loop execution using new_event_loop (replaced asyncio.run)
- shutdown_asyncgens() called before loop.close()
- C1-FIX comment present
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.c5")

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

async def test_event_loop_replaced():
    """Verify shared global event loop was replaced with per-task execution."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "C1-FIX comment present explaining new_event_loop pattern",
        "C1-FIX: Per-task event loop execution" in content
    )
    check(
        "new_event_loop() used instead of asyncio.run()",
        "asyncio.new_event_loop()" in content
    )
    check(
        "run_until_complete used for coroutine execution",
        "loop.run_until_complete(coro)" in content
    )

async def test_shutdown_asyncgens():
    """Verify shutdown_asyncgens() is called before loop.close()."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "shutdown_asyncgens() called in finally block",
        "loop.shutdown_asyncgens()" in content
    )
    check(
        "shutdown_asyncgens appears before loop.close()",
        content.index("shutdown_asyncgens") < content.index("loop.close()")
    )
    check(
        "loop.close() called in finally block",
        "loop.close()" in content
    )

async def test_phase_split():
    """Verify _run() splits DB transactions into phases (fix 1.1)."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "PHASE 1 comment present (pre-AI transaction)",
        "PHASE 1: Pre-AI processing" in content
    )
    check(
        "PHASE 2 comment present (no DB transaction)",
        "PHASE 2: AI Gateway processing (NO DB transaction)" in content
    )
    check(
        "PHASE 3 comment present (post-AI transaction)",
        "PHASE 3: Post-AI processing (new DB transaction)" in content
    )

def main():
    asyncio.run(test_event_loop_replaced())
    asyncio.run(test_shutdown_asyncgens())
    asyncio.run(test_phase_split())

    total = PASSED + FAILED
    logger.info("C-5 Results: %d/%d passed", PASSED, total)
    result = {"test": "C-5 Event Loop Isolation", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
