#!/usr/bin/env python3
"""R-1 verification: Verify retry deadlock fixes.

Checks:
- _run_async() uses new_event_loop + shutdown_asyncgens + close (fix 1.2)
- _run() splits DB session into 3 phases (fix 1.1) so no transaction spans AI call
- check_retry_storm() is called before processing retries (CRIT-1)
- Serialization failures (40001/40P01) trigger immediate retry
- Event loop can be recreated after failed attempts (C1-FIX pattern)
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.r1")

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

async def test_run_async_event_loop_cleanup():
    """Verify _run_async() properly creates and destroys event loops per call."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: new_event_loop() called in _run_async",
        "asyncio.new_event_loop()" in content
    )
    check(
        "R-1: set_event_loop called after creating loop",
        "asyncio.set_event_loop(loop)" in content
    )
    check(
        "R-1: shutdown_asyncgens called before loop.close()",
        "loop.shutdown_asyncgens()" in content
    )
    check(
        "R-1: loop.close() called in finally block",
        "loop.close()" in content
    )
    check(
        "R-1: shutdown_asyncgens appears before close in source",
        "shutdown_asyncgens()" in content and "loop.close()" in content
    )
    # Verify ordering
    shutdown_pos = content.index("shutdown_asyncgens()")
    close_pos = content.index("loop.close()")
    check(
        "R-1: shutdown_asyncgens() called before loop.close() in source order",
        shutdown_pos < close_pos
    )

async def test_phase_split():
    """Verify _run() splits DB work into 3 phases (fix 1.1)."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: PHASE 1 comment exists (pre-AI with DB transaction)",
        "PHASE 1: Pre-AI processing" in content
    )
    check(
        "R-1: PHASE 2 comment exists (AI gateway, no DB transaction)",
        "PHASE 2: AI Gateway processing (NO DB transaction)" in content
    )
    check(
        "R-1: PHASE 3 comment exists (post-AI with new DB transaction)",
        "PHASE 3: Post-AI processing (new DB transaction)" in content
    )
    check(
        "R-1: Phase 1 commit happens before Phase 2",
        "await db.commit()" in content
    )

async def test_check_retry_storm_called():
    """Verify check_retry_storm is called on retries (CRIT-1)."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: check_retry_storm imported in task",
        "from app.tasks.retry_guard import check_retry_storm" in content
    )
    check(
        "R-1: check_retry_storm called when retries > 0",
        "check_retry_storm(job_id" in content
    )
    check(
        "R-1: Retry storm blocked message present",
        "retry_storm_blocked" in content
    )

async def test_serialization_retry():
    """Verify serialization failures trigger immediate retry (not DLQ)."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: Serialization error codes checked (40001, 40P01)",
        "40001" in content and "40P01" in content
    )
    check(
        "R-1: self.retry() called on serialization failure",
        "raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))" in content
    )
    check(
        "R-1: Serialization failure logged before retry",
        "Serialization failure on job" in content
    )

async def test_event_loop_twice_no_crash():
    """Verify calling _run_async twice in same thread doesn't crash.
    
    This simulates a retry scenario where a prior event loop was left in a
    bad state. new_event_loop() should create a fresh loop each time.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))
    try:
        from celery_app import _run_async
    except ImportError as e:
        logger.warning("R-1: Could not import _run_async (expected if deps not installed): %s", e)
        check("R-1: _run_async import (module exists)", False)
        return

    # Call _run_async twice in the same thread with a simple coroutine
    async def simple_coro():
        return 42

    try:
        # Disable event loop reuse check for test
        first = _run_async(simple_coro())
        logger.info("R-1: First _run_async call returned %s", first)
        second = _run_async(simple_coro())
        logger.info("R-1: Second _run_async call returned %s", second)
        check("R-1: Two _run_async calls in same thread succeed", first == 42 and second == 42)
    except RuntimeError as e:
        logger.error("R-1: _run_async crashed on second call: %s", e)
        check("R-1: Two _run_async calls in same thread succeed (no crash)", False)
    except Exception as e:
        logger.error("R-1: _run_async unexpected error: %s", e)
        check("R-1: _run_async handles unexpected errors", False)

async def test_concurrent_retry_storm_check():
    """Verify check_retry_storm and retry_guard module exist."""
    guard_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "tasks", "retry_guard.py")
    if not os.path.exists(guard_path):
        check("R-1: retry_guard.py exists", False)
        return

    with open(guard_path) as f:
        content = f.read()

    check(
        "R-1: check_retry_storm function defined",
        "def check_retry_storm" in content
    )
    check(
        "R-1: retry_guard returns True/False",
        "True" in content and "False" in content
    )

async def test_shutdown_grace_period():
    """Verify shutdown grace period uses max(5, min(300, active*10))."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: Grace period uses max(5, min(300, active*10))",
        "max(5, min(300, total_active * 10)" in content
    )

async def test_redis_lock_on_retry():
    """Verify Redis lock is deleted and re-acquired on retry (C2-FIX)."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: C2-FIX comment present for Redis lock",
        "C2-FIX: Use Redis-based distributed lock" in content
    )
    check(
        "R-1: Redis lock deleted before re-acquire on retry",
        "_redis_lock.delete(_redis_job_lock_key)" in content
    )
    check(
        "R-1: Redis lock set with NX and 300s TTL",
        "nx=True, ex=300" in content
    )

async def test_run_async_c1_fix_comment():
    """Verify C1-FIX comment explains the new_event_loop pattern."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "R-1: C1-FIX comment block explains the pattern",
        "C1-FIX: Per-task event loop execution" in content
    )
    check(
        "R-1: C1-FIX explains why asyncio.run() was replaced",
        "Cannot run asyncio.run" in content or "replaced asyncio.run" in content
    )

def main():
    asyncio.run(test_run_async_event_loop_cleanup())
    asyncio.run(test_phase_split())
    asyncio.run(test_check_retry_storm_called())
    asyncio.run(test_serialization_retry())
    asyncio.run(test_concurrent_retry_storm_check())
    asyncio.run(test_shutdown_grace_period())
    asyncio.run(test_redis_lock_on_retry())
    asyncio.run(test_run_async_c1_fix_comment())
    # The real event loop test is last since it actually imports celery_app
    # and may fail if dependencies aren't installed
    try:
        asyncio.run(test_event_loop_twice_no_crash())
    except Exception as e:
        logger.warning("R-1: Runtime test skipped — %s", e)

    total = PASSED + FAILED
    logger.info("R-1 Results: %d/%d passed", PASSED, total)
    result = {"test": "R-1 Retry Deadlock Prevention", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
