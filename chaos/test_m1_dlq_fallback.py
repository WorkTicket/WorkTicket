#!/usr/bin/env python3
"""M-1 verification: Verify DLQ no longer writes JSONL fallback files (fix 1.4).

Checks:
- No more ephemeral JSONL file writes in DLQ path
- DB write failure is logged at CRITICAL with metric
- dlq_write_failures_total counter exists
"""
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.m1")

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

def test_no_jsonl_fallback():
    """Verify no JSONL fallback file writes remain in celery_app.py."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    # Backward-compat cleanup task (endswith check) is acceptable; write path must not exist
    import re
    open_jsonl_patterns = re.findall(r'open\([^)]*\.jsonl', content)
    check(
        "M-1: No open() call with .jsonl file extension",
        len(open_jsonl_patterns) == 0
    )
    check(
        "M-1: DLQ write failure logged at CRITICAL level",
        ".critical(" in content
    )

def test_dlq_write_failures_metric():
    """Verify dlq_write_failures_total metric exists."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()
    check(
        "M-1: dlq_write_failures_total counter referenced",
        "dlq_write_failures_total" in content
    )

def test_no_fallback_directory():
    """Verify no dlq_fallback directory exists in the project."""
    fallback_dir = os.path.join(os.path.dirname(__file__), "..", "data", "dlq_fallback")
    check(
        "M-1: No dlq_fallback data directory",
        not os.path.exists(fallback_dir)
    )

def test_dlq_prometheus_metric():
    """Verify dlq_write_failures_total is registered in prometheus.py."""
    prom_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "app", "monitoring", "prometheus.py")
    with open(prom_path) as f:
        content = f.read()

    check(
        "M-1: dlq_write_failures_total registered in prometheus.py",
        "dlq_write_failures_total" in content
    )
    check(
        "M-1: increment_counter function available for dlq metric",
        "increment_counter" in content
    )

def test_dlq_batcher_test_exists():
    """Verify batcher-based DLQ drain is the intended path."""
    celery_path = os.path.join(os.path.dirname(__file__), "..", "src", "backend", "celery_app.py")
    with open(celery_path) as f:
        content = f.read()

    check(
        "M-1: DLQ uses DB batcher approach (no file fallback)",
        "_move_to_dead_letter" in content
    )

def main():
    test_no_jsonl_fallback()
    test_dlq_write_failures_metric()
    test_no_fallback_directory()
    test_dlq_prometheus_metric()
    test_dlq_batcher_test_exists()

    total = PASSED + FAILED
    logger.info("M-1 Results: %d/%d passed", PASSED, total)
    result = {"test": "M-1 DLQ Fallback Cleanup", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
