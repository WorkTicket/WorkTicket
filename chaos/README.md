# Chaos Tests

This directory contains destructive chaos engineering tests that validate WorkTicket's resilience against infrastructure failures, race conditions, and edge cases.

## Test Categories

### Hardening Verification

These are **source-code verification tests** — they inspect the codebase for required patterns rather than running against a live system. They validate that critical fixes and protections are in place and have not regressed.

#### Data Integrity

| Test | What it verifies | Type |
|------|------------------|------|
| `test_c1_silent_rollback.py` | Silent rollback detection — commits on success path, metrics, alerting | Static analysis |
| `test_c2_stalled_job_recovery.py` | Stalled job recovery — commits transitions in scan_for_stalled_ai_jobs | Static analysis |

#### Concurrency & Isolation

| Test | What it verifies | Type |
|------|------------------|------|
| `test_c4_concurrency_limit.py` | Concurrency limit enforcement — semaphore guards | Static analysis |
| `test_c5_event_loop_isolation.py` | Event loop isolation — thread-local loops | Static analysis |
| `test_h2_idempotency.py` | Idempotency isolation — dedup keys per request | Static analysis |

#### Queue Resilience & Backpressure

| Test | What it verifies | Type |
|------|------------------|------|
| `test_h5_queue_backpressure.py` | Per-queue backpressure — depth checks before enqueue | Static analysis |
| `test_m1_dlq_fallback.py` | Dead-letter queue fallback — maxlen, TTL, compaction | Static analysis |
| `test_r1_retry_deadlock.py` | Retry deadlock prevention — lock refresh strategy | Static analysis |

#### Webhook & WebSocket

| Test | What it verifies | Type |
|------|------------------|------|
| `test_c3_stripe_webhook.py` | Stripe webhook validation — signature verification, idempotency | Static analysis |
| `test_h7_ws_global_count.py` | WebSocket global count accuracy | Static analysis |

**Run time:** ~5-10 seconds total  
**Requirements:** None (reads source files only)  
**When to run:** Every PR, CI pipeline

---

### Infrastructure Chaos Tests (Original)

These tests run against a **live Docker Compose stack** and inject real failures (kill containers, network partitions, resource exhaustion).

| Test | Failure Injected | Duration | Pass Criteria |
|------|------------------|----------|---------------|
| `redis_failover.py` | Redis broker full outage | 15 min | System returns 429 during outage; no 503s after recovery |
| `redis_outage.py` | Redis 15-min outage (K2) | 15 min | DB poll amplification <10x; health recovers |
| `connection_spike.py` | Connection pool exhaustion | ~2 min | No leaked connections; pool recovers |
| `billing_contention.py` | Concurrent billing operations | ~1 min | No lost updates; serializable isolation |
| `simulate_webhook_flood.py` | 1000+ Stripe webhooks/sec | ~30 sec | Idempotency holds; no duplicate processing |
| `celery_worker_kill.py` | Worker kill mid-task | ~1 min | Task requeued; no data loss; lock released |

**Run time:** ~20-30 minutes total (sequential)  
**Requirements:**
- Full Docker Compose stack running (`docker compose up -d`)
- Healthy backend at `http://localhost:8000`
- Redis container named `workticket-redis-broker-1`
- Test database with migrations applied

**When to run:**
- **Pre-release only** (tagged releases, RC candidates)
- **Not in normal CI** — too slow, requires live infrastructure
- Manual execution by release engineer

---

## Running the Tests

### Hardening Verification (Fast, No Infrastructure)

```bash
cd chaos
python run_all.py
```

Expected output:
```
============================================================
Chaos Test Suite — 2026-01-15T10:30:00
Running 16 tests

============================================================
STARTING: C-1 Silent Rollback Detection
============================================================
C-1: Silent rollback detection test
  PASS: Phase 1 commit present (PHASE 1: Pre-AI processing)
  PASS: Phase 2 marker present (NO DB transaction)
  PASS: Phase 3 commit (post-AI) present
  PASS: Phase 1 explicit db.commit() present
  PASS: commit error handled with try/except
  ...
C-1 Results: 12/12 passed
{"test": "C-1 Silent Rollback Detection", "passed": 12, "failed": 0, "total": 12}

...

============================================================
RESULTS SUMMARY
============================================================
Total: 16 | Passed: 16 | Failed: 0
  [PASS] C-1 Silent Rollback Detection (2.1s)
  [PASS] C-2 Stalled Job Recovery (1.8s)
  ...
```

### Infrastructure Chaos Tests (Slow, Requires Live Stack)

```bash
# 1. Start full stack
cd backend
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose up -d

# 2. Verify health
curl http://localhost:8000/healthz
# {"status": "healthy", ...}

# 3. Run specific chaos test
cd ../chaos
python redis_failover.py
# or
python run_all.py  # runs ALL including infra tests (20+ min)
```

**Note:** Infrastructure tests modify running containers. Run on a dedicated staging environment, not your development machine.

---

## Adding a New Chaos Test

1. Create `test_<name>.py` in `chaos/`
2. Follow the pattern:
   - Output JSON to stdout with `{"passed": bool, ...}`
   - Exit code 0 = pass, non-zero = fail
   - Use `logging` for structured output
3. Add entry to `TESTS` list in `run_all.py`
4. Document in this README

### Static Analysis Test Template

```python
#!/usr/bin/env python3
"""Description of what this test verifies."""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.<name>")

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

async def test_<name>():
    # Read source files, verify patterns exist
    ...

def main():
    asyncio.run(test_<name>())
    total = PASSED + FAILED
    logger.info("<Name> Results: %d/%d passed", PASSED, total)
    result = {"test": "<Name>", "passed": PASSED, "failed": FAILED, "total": total}
    print(json.dumps(result))
    sys.exit(0 if FAILED == 0 else 1)

if __name__ == "__main__":
    main()
```

### Infrastructure Test Template

```python
#!/usr/bin/env python3
"""Chaos test: <failure description>."""

import asyncio
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chaos.<name>")

async def run():
    results = {"passed": True}
    # Inject failure, verify behavior, restore
    return results

if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("passed") else 1)
```

---

## Report Output

`run_all.py` produces `chaos_report.json`:

```json
{
  "timestamp": "2026-01-15T10:30:45",
  "total": 16,
  "passed": 16,
  "failed": 0,
  "results": [
    {"name": "C-1 Silent Rollback Detection", "script": "test_c1_silent_rollback.py", "duration_seconds": 2.1, "return_code": 0, "passed": true, ...},
    ...
  ]
}
```

Archive this report with release artifacts for audit trail.

---

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) — Development workflow, PR process, and code standards
- [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) — Community standards and enforcement
- [SECURITY.md](../SECURITY.md) — Vulnerability disclosure and security practices
- `ops-guide.md` — Deploy sequencing, Redis Sentinel HA, rollback drills
- `docs/runbooks/` — Incident response: Redis OOM, DLQ fallback, circuit breaker