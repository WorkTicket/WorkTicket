#!/usr/bin/env python3
"""Orchestrator: run all chaos tests sequentially with reporting."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.orchestrator")

TESTS = [
    # Phase 4 — Chaos Tests for Remediation Fixes
    ("C-1 Silent Rollback Detection", "test_c1_silent_rollback.py"),
    ("C-2 Stalled Job Recovery", "test_c2_stalled_job_recovery.py"),
    ("C-3 Stripe Webhook Validation", "test_c3_stripe_webhook.py"),
    ("C-4 Concurrency Limit Enforcement", "test_c4_concurrency_limit.py"),
    ("C-5 Event Loop Isolation", "test_c5_event_loop_isolation.py"),
    ("H-2 Idempotency Isolation", "test_h2_idempotency.py"),
    ("H-5 Per-Queue Backpressure", "test_h5_queue_backpressure.py"),
    ("H-7 WS Global Count Accuracy", "test_h7_ws_global_count.py"),
    ("M-1 DLQ Fallback Cleanup", "test_m1_dlq_fallback.py"),
    ("R-1 Retry Deadlock Prevention", "test_r1_retry_deadlock.py"),
    # Original chaos tests
    ("Redis Failover", "redis_failover.py"),
    ("Connection Spike", "connection_spike.py"),
    ("Billing Contention", "billing_contention.py"),
    ("Webhook Flood", "simulate_webhook_flood.py"),
    ("Celery Worker Kill", "celery_worker_kill.py"),
]


def run_test(name: str, script: str) -> dict:
    logger.info("=" * 60)
    logger.info("STARTING: %s", name)
    logger.info("=" * 60)

    script_path = os.path.join(os.path.dirname(__file__), script)
    start = time.time()

    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True, text=True, timeout=600,
    )

    duration = time.time() - start
    output = result.stdout.strip()

    try:
        test_results = json.loads(output)
    except json.JSONDecodeError:
        test_results = {"raw_stdout": output, "raw_stderr": result.stderr.strip()}

    test_results["name"] = name
    test_results["script"] = script
    test_results["duration_seconds"] = round(duration, 1)
    test_results["return_code"] = result.returncode
    test_results["passed"] = test_results.get("passed", result.returncode == 0)

    status = "PASSED" if test_results["passed"] else "FAILED"
    logger.info("%s: %s (%.1fs)", name, status, duration)

    if result.stderr.strip():
        test_results["stderr"] = result.stderr.strip()

    return test_results


def main():
    results = []
    passed = 0
    failed = 0

    logger.info("Chaos Test Suite — %s", datetime.utcnow().isoformat())
    logger.info("Running %d tests\n", len(TESTS))

    for name, script in TESTS:
        test_result = run_test(name, script)
        results.append(test_result)
        if test_result["passed"]:
            passed += 1
        else:
            failed += 1
        print()  # spacing

    # Summary
    logger.info("=" * 60)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info("Total: %d | Passed: %d | Failed: %d", len(results), passed, failed)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        logger.info("  [%s] %s (%.1fs)", status, r["name"], r["duration_seconds"])

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    report_path = os.path.join(os.path.dirname(__file__), "chaos_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("\nReport saved to: %s", report_path)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
