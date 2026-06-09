#!/usr/bin/env python3
"""H-7 verification: Verify WebSocket global connection count accuracy.

Checks:
- SADD/SREM/SCARD used instead of INCR/DECR
- Member ID stored in handler context for accurate cleanup
- Local fallback maintains correctness
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.h7")

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

async def test_sadd_srem_scard():
    """Verify SADD/SREM/SCARD used instead of INCR/DECR."""
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "ai", "router.py")
    with open(router_path) as f:
        content = f.read()

    check(
        "SADD used for global connection tracking",
        "sadd" in content
    )
    check(
        "SREM used for global connection decrement",
        "srem" in content
    )
    check(
        "SCARD used for global connection count",
        "scard" in content
    )
    check(
        "INCR no longer used for global count",
        "incr" not in content.split("_increment_ws_global")[1].split("def _decrement")[0] if "_increment_ws_global" in content else True
    )
    check(
        "Member UUID generated for each connection",
        "str(uuid.uuid4())" in content
    )

async def test_member_passed_to_decrement():
    """Verify member is passed through to _decrement_ws_global."""
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "ai", "router.py")
    with open(router_path) as f:
        content = f.read()

    check(
        "_increment_ws_global returns (bool, str) tuple",
        "tuple[bool, str]" in content
    )
    check(
        "Member stored in handler as _ws_global_member",
        "_ws_global_member" in content
    )
    check(
        "Member passed to _decrement_ws_global on disconnect",
        "_decrement_ws_global(_ws_global_member" in content
    )

async def test_local_fallback():
    """Verify local fallback still works correctly."""
    router_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "ai", "router.py")
    with open(router_path) as f:
        content = f.read()

    check(
        "Local fallback uses threading Lock",
        "_ws_global_count_lock" in content
    )
    check(
        "Local increment returns member too",
        "return True, member" in content
    )

def main():
    asyncio.run(test_sadd_srem_scard())
    asyncio.run(test_member_passed_to_decrement())
    asyncio.run(test_local_fallback())

    total = PASSED + FAILED
    logger.info("H-7 Results: %d/%d passed", PASSED, total)
    result = {"test": "H-7 WebSocket Global Count Accuracy", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
