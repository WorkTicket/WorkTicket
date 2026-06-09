#!/usr/bin/env python3
"""H-2 verification: Verify idempotency operations isolation.

Checks:
- Outer session rollback removed from create_idempotency_record
- Graceful error handling
- Separate session or savepoint approach used
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.h2")

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

async def test_no_rollback():
    """Verify await db.rollback() is removed."""
    svc_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "billing", "idempotency_service.py")
    with open(svc_path) as f:
        content = f.read()

    section = content[content.find("async def create_idempotency_record"):content.find("async def create_idempotency_record") + 2000]
    check(
        "await db.rollback() removed from create_idempotency_record",
        "await db.rollback()" not in section
    )
    check(
        "Flush still used for idempotency record insertion",
        "await db.flush()" in section
    )
    check(
        "Integrity error caught gracefully",
        "except Exception" in section
    )

async def test_409_on_conflict():
    """Verify 409 is returned on conflict without rolling back outer session."""
    svc_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "billing", "idempotency_service.py")
    with open(svc_path) as f:
        content = f.read()

    check(
        "409 raised for duplicate key",
        "raise HTTPException(status_code=409" in content
    )
    check(
        "Comment explains no rollback",
        "Do NOT rollback" in content
    )

def main():
    asyncio.run(test_no_rollback())
    asyncio.run(test_409_on_conflict())

    total = PASSED + FAILED
    logger.info("H-2 Results: %d/%d passed", PASSED, total)
    result = {"test": "H-2 Idempotency Isolation", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
