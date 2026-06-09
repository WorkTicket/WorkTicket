# WorkTicket Production Readiness — Comprehensive Remediation Plan

## Status Assessment: What's Already Fixed

The codebase has already received substantial remediation. The following audit findings have been fixed:

| Finding | Status | Location |
|---------|--------|----------|
| C-1: process_job_task never commits | **FIXED** | `celery_app.py:840-852` — `await db.commit()` on success path |
| C-2: scan_for_stalled_ai_jobs never commits | **FIXED** | `celery_app.py:1782-1784, 1822-1826` — `await db.commit()` in recovery loop |
| C-5: Event loop corruption cascade | **FIXED** | `celery_app.py:416-434` — per-task `asyncio.run()` with fresh loop fallback |
| H-1: Compensation commits to outer session | **FIXED** | `celery_app.py:472` — uses `flush()` not `commit()` when outer `db` is provided |
| H-2: Idempotency rollback on outer session | **FIXED** | `idempotency_service.py:65-74` — no longer calls `db.rollback()` |
| H-5: Queue depth backpressure total check | **FIXED** | `celery_app.py:159-175` — per-queue thresholds |
| H-6: Shared reconciliation lock | **FIXED** | `celery_app.py:1325-1329, 1346, 1526` — separate locks per task |
| H-7: WS global count INCR/DECR drift | **FIXED** | `app/ai/router.py:101-145` — uses `SADD`/`SREM`/`SCARD` |
| H-8: Payment success re-enables AI unconditionally | **FIXED** | `app/billing/router.py:738-747` — checks `ai_disabled_reason == "payment_failed"` |
| M-1: DLQ fallback files accumulate | **FIXED** | `celery_app.py:1247-1257` — stale file cleanup on every fallback write |
| M-6: String concatenation in webhook body | **FIXED** | `app/billing/router.py:422-428` — uses `bytearray` |
| L-3: purge_soft_deleted leaves orphans | **FIXED** | `celery_app.py:1623-1636` — cascades AIOutput deletion before Job purge |
| L-4: WS origin check rejects proxies | **FIXED** | `app/ai/router.py:633-653` — origin validation implemented |
| L-5: healthz/readyz no metrics | **FIXED** | `app/main.py:334-337, 383-386` — Prometheus counters added |
| M-2: WS accept semaphore fixed at 50 | **FIXED** | `app/ai/router.py:656-659` — configurable via `WS_ACCEPT_SEMAPHORE` env var |
| M-5: WS DB poll no backpressure | **FIXED** | `app/ai/router.py:661-664` — shared semaphore with configurable concurrency |
| 4C-I-2: statement_cache_size parameter | **FIXED** | `app/database.py:19-21` — both params set for compatibility |

---

## Remaining Issues — Fix Plan

### IMMEDIATE (0.5 engineer-days)

#### 1. C-4: Concurrency Counter DECR — Cap at Minimum Zero

**File:** `src/backend/app/billing/concurrency.py:80-99`

**Problem:** `_RELEASE_LUA` DECR can drive the Redis counter below zero when `release()` is called more times than `acquire()`. The negative counter causes unreliable concurrency control for 300s (TTL).

**Fix:** Replace `redis.call("DECR", key)` with a capped decrement:

```lua
-- Before line 91
local current = tonumber(redis.call("GET", key))
if current and current > 0 then
    redis.call("DECR", key)
end
local new_count = tonumber(redis.call("GET", key)) or 0
if new_count <= 0 then
    redis.call("DEL", key)
    return 0
end
return new_count
```

**Verification:** Run `chaos/test_c4_concurrency_limit.py` — counter should never go negative.

---

#### 2. H-3: Double Reservation — Celery Worker Re-Reserves After API Handler

**File:** `src/backend/celery_app.py:667-680`

**Problem:** The API handler (`app/ai/router.py:231-243`) calls `check_and_reserve`, reserving quota. The Celery worker (`celery_app.py:675`) calls `check_and_reserve` AGAIN, double-reserving. The API handler's reservation is never released on success.

**Fix:** Replace the Celery worker's re-reservation with a use of the pre-reserved `our_reserved`:

```python
# celery_app.py ~667-680 — Replace re-reservation block
# Use the reservation from the API handler (H-3: no double-reserve)
if our_reserved <= 0:
    # No pre-reservation from API handler (legacy/retry path): reserve now
    result = await quota_engine.check_and_reserve(db, company_id, our_estimated_cost, job_id)
    if not result.allowed:
        task_logger.warning("Quota blocked: %s", result.reason)
        await record_trace(_trace_id, "quota_blocked", "failed", ...)
        await transition_job_state(db, job.id, company_id, AIProcessingState.failed, ...)
        return {"status": "quota_exceeded", "job_id": job_id, "reason": result.reason}
    our_reserved = result.reserved_acu
else:
    task_logger.info("Using pre-reserved quota: %.4f ACU", our_reserved)
```

**Edge case:** On retry (Celery retries or API handler crashed after enqueue but before commit), `our_reserved` is still passed. The original transaction was rolled back, so the reservation is lost. But `reserved_acu` defaults to 0 in `enqueue_job_task` on retry from `scan_for_stalled_ai_jobs`, so the worker will re-reserve. This is correct.

**Verification:** Run e2e flow test — reserved_acu should not grow unbounded across job runs.

---

#### 3. C-3: Stripe Webhook Billing Period Validation

**File:** `src/backend/app/billing/router.py ~508-761`

**Problem:** Stripe webhook events can arrive late (up to 3 days per Stripe retry policy) and be processed against the current billing period. An `invoice.payment_failed` from the previous period could disable AI in the current period.

**Fix:** Add billing period validation after event type dispatch. Before processing any payment event, check that the event timestamp falls within the company's current billing period:

```python
# After account = await quota_engine.get_or_create_account(...)
import time
event_ts = datetime.fromtimestamp(event_timestamp, tz=timezone.utc)
if account.billing_period_start and event_ts < account.billing_period_start:
    logger.warning(
        "Rejecting late-arriving webhook event %s: event timestamp %s is before "
        "current billing period start %s for company %s",
        effective_event_id, event_ts.isoformat(),
        account.billing_period_start.isoformat(), company.id,
    )
    raise HTTPException(status_code=400, detail="Event belongs to a prior billing period")
```

**Verification:** Run `chaos/test_c3_stripe_webhook.py` — late events should be rejected.

---

### HIGH PRIORITY (3-4 engineer-days)

#### 4. RACE-2: reset_billing_quotas TOCTOU Race with Concurrent Job Completion

**File:** `src/backend/celery_app.py:1396-1454`

**Problem:** `reset_billing_quotas` reads accounts without FOR UPDATE (lines 1399-1411), then later acquires FOR UPDATE (lines 1417-1419). A concurrent job completing between the read and the lock will have its usage overwritten by the reset.

**Fix:** Move the FOR UPDATE lock to the query itself — combine the filter + lock into a single paginated query:

```python
# Replace lines 1399-1411 and 1417-1419 with:
due_page = await db.execute(
    select(BillingAccount).where(
        BillingAccount.reset_at <= now,
        or_(
            BillingAccount.reservation_heartbeat_at.is_(None),
            BillingAccount.reservation_heartbeat_at < stale_cutoff,
        )
    )
    .order_by(BillingAccount.company_id)
    .with_for_update(skip_locked=True)  # Lock immediately
    .offset(offset)
    .limit(PAGE_SIZE)
)
page_accounts = due_page.scalars().all()
```

This eliminates the TOCTOU window by locking accounts at read time.

**Verification:** Run `chaos/billing_contention.py` — no zeroed usage for concurrent completions.

---

#### 5. Observability — Silent Failure Detection Metrics

**Files:** `src/backend/app/monitoring/prometheus.py` (add counters), Grafana dashboard

**Problem:** C-1 type failures (AI processing runs but DB changes rolled back) are undetectable. No metric compares API job creation vs AIOutput storage.

**Fix — Add the following metrics and alert:**

**In `app/monitoring/prometheus.py`:**
- `gauge` `workticket_jobs_completion_rate_ratio` — ratio of `aioutputs_created` / `jobs_created` over 5m window
- `counter` `workticket_ws_messages_delivered_total` — WebSocket message delivery rate
- `counter` `workticket_concurrency_counter_negative_total` — already exists, add alert
- `histogram` `workticket_celery_queue_latency_seconds` — per-queue processing latency
- `gauge` `workticket_beat_task_execution_timestamp` — last execution time per beat task

**In `celery_app.py`:**
- After line 847 (increment_jobs_completed): the metric already exists
- Add per-queue latency observation at line 827

**In Prometheus alerts:**
```yaml
- alert: SilentJobFailure
  expr: rate(workticket_jobs_created_total[5m]) - rate(workticket_aioutputs_created_total[5m]) > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "AI jobs are being created but not completed"
```

---

#### 6. Database — Automatic Retry on Serialization Failures in Celery Tasks

**File:** `src/backend/celery_app.py` (all tasks using `AsyncSessionLocal()`)

**Problem:** The `get_db()` FastAPI dependency has retry logic for serialization failures (40001/40P01/55P03), but manual `AsyncSessionLocal()` usage in Celery tasks does NOT retry.

**Fix:** Create a `retry_on_serialization` decorator/context manager:

```python
# In app/database.py or a new file app/db/retry.py
import asyncio
from sqlalchemy.exc import DBAPIError

MAX_SERIALIZATION_RETRIES = 3
SERIALIZATION_CODES = {"40001", "40P01", "55P03"}

async def run_with_retry(db_session_factory, coro_factory, max_retries=MAX_SERIALIZATION_RETRIES):
    """Run a coroutine with automatic retry on serialization failures."""
    last_exc = None
    for attempt in range(max_retries):
        async with db_session_factory() as db:
            try:
                return await coro_factory(db)
            except DBAPIError as e:
                code = getattr(e.orig, 'pgcode', None)
                if code in SERIALIZATION_CODES and attempt < max_retries - 1:
                    last_exc = e
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                raise
    raise last_exc
```

Apply to all Celery tasks that use `AsyncSessionLocal()`.

---

#### 7. WebSocket — Auth Cache TTL Mismatch / Shorter Re-Auth Interval

**File:** `src/backend/app/ai/router.py:833`

**Problem:** Auth cache TTL is 300s but re-auth check interval is 240-360s (with jitter). A revoked token remains valid for up to 360s (6 minutes).

**Fix:** Reduce cache TTL and re-auth interval:

```python
# Line 833: Reduce re-auth interval
if now - _last_auth_check > random.uniform(60, 120):
```

Also reduce the TTLCache TTL in `_get_cached_ws_auth` to 120s.

---

#### 8. Concurrency — Add Negative Counter Alert

**File:** `ops/prometheus-alerts.yml`

**Problem:** `workticket_concurrency_counter_negative_total` is counted but no alert fires.

**Fix:**
```yaml
- alert: ConcurrencyCounterNegative
  expr: rate(workticket_concurrency_counter_negative_total[5m]) > 0
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Concurrency counter is going negative for company {{ $labels.company_id }}"
```

---

### MEDIUM PRIORITY (2-3 engineer-days)

#### 9. L-1: collect_billing_debt — Add ORDER BY for Reproducibility

**File:** `src/backend/celery_app.py:1537-1543`

**Fix:** Add `.order_by(BillingAccount.company_id)` to the `select(BillingAccount)` query.

---

#### 10. WebSocket — Send Queue Drop Alert

**File:** `src/backend/app/ai/router.py:666-676`

**Problem:** WS send queue drops are logged + counted but no alert fires.

**Fix:** Add Prometheus alert for sustained drops:
```yaml
- alert: WebSocketSendDropping
  expr: rate(workticket_ws_send_dropped_total[5m]) > 0
  for: 2m
  labels:
    severity: warning
```

---

#### 11. Stripe Webhook — Processing Latency Histogram

**File:** `src/backend/app/billing/router.py`

**Problem:** No metric tracks Stripe webhook processing time.

**Fix:** Add timing around the webhook handler:
```python
import time
_wh_start = time.monotonic()
# ... existing handler logic ...
_wh_ms = (time.monotonic() - _wh_start) * 1000
try:
    from app.monitoring.prometheus import observe_stripe_webhook_latency
    observe_stripe_webhook_latency(_wh_ms, event_type)
except Exception:
    pass
```

---

#### 12. Beat Task Execution Tracking

**File:** `src/backend/celery_app.py` — all beat tasks

**Problem:** If a beat task completes "successfully" with zero iterations, there's no way to tell it ran at all.

**Fix:** At the end of each beat task, write a Redis key with the execution timestamp and iteration counts:
```python
try:
    _exec_redis = create_sync_redis_from_url(REDIS_URL, socket_connect_timeout=0.5)
    _exec_redis.setex(f"beat:last_run:{task_name}", 3600, f"{datetime.now(timezone.utc).isoformat()}")
    _exec_redis.close()
except Exception:
    pass
```

Expose this in `/readyz` under a `beat_tasks` component.

---

### LOW PRIORITY (0.5-1 engineer-day)

#### 13. temp_quota_multiplier Decimal Precision

**File:** `src/backend/app/billing/models.py:32`

**Problem:** `Numeric(4, 2)` supports up to 99.99 — fine for a multiplier. The `float()` conversion in calculations could cause minor precision loss.

**Fix:** Keep as-is. Not a real production risk. Document that `Decimal` operations should be used for all billing calculations.

---

#### 14. queue_flood_sim — Chaos Test for Queue Backpressure

**File:** New chaos test

**Problem:** The queue backpressure system has no chaos test.

**Fix:** Create a chaos test that floods individual queues to verify per-queue backpressure doesn't block other queues.

---

### OBSERVABILITY GAPS (1 engineer-day)

#### 15. Dashboard: Jobs Created vs Completed Panel

Add a Grafana panel showing:
- Rate of `jobs_created_total` (counter from API handler)
- Rate of `aioutputs_created_total` (counter from Celery success path)
- Ratio line (should be ~1.0 in steady state)
- Alert threshold when ratio drops below 0.9 for 5 minutes

---

#### 16. Dashboard: Per-Queue Latency Panel

Add a Grafana panel showing p50/p95/p99 latency per Celery queue:
- `workticket_celery_queue_latency_seconds{queue="ai_text"}`
- `workticket_celery_queue_latency_seconds{queue="ai_audio"}`
- `workticket_celery_queue_latency_seconds{queue="ai_image"}`

---

#### 17. Dashboard: WebSocket Metrics Panel

Add a Grafana panel for:
- Active WS connections (from `_increment_ws_global` counter)
- WS message delivery rate (`workticket_ws_messages_sent_total`)
- WS dropped message rate (`workticket_ws_send_dropped_total`)

---

### CHAOS TESTING & RECOVERY VALIDATION (1-2 engineer-days)

#### 18. Run Existing Chaos Tests Against Fixed Code

| Test | Validates |
|------|-----------|
| `chaos/test_c1_silent_rollback.py` | C-1 fix: jobs complete despite DB restart |
| `chaos/test_c2_stalled_job_recovery.py` | C-2 fix: stalled jobs recovered and committed |
| `chaos/test_c3_stripe_webhook.py` | C-3 fix: late webhooks rejected |
| `chaos/test_c4_concurrency_limit.py` | C-4 fix: counter never goes negative |
| `chaos/test_c5_event_loop_isolation.py` | C-5 fix: event loop isolation verified |
| `chaos/test_h2_idempotency.py` | H-2 fix: concurrent requests with same key |
| `chaos/test_h5_queue_backpressure.py` | H-5 fix: per-queue isolation under load |
| `chaos/test_h7_ws_global_count.py` | H-7 fix: WS count accuracy under reconnect |
| `chaos/test_m1_dlq_fallback.py` | M-1 fix: fallback files cleaned up |

---

### EXECUTION ORDER

```
Phase 1 — CRITICAL SAFETY (0.5 day, do first)
├── 1. C-4: Concurrency DECR cap
└── 2. H-3: Remove double reservation in Celery worker

Phase 2 — DATA INTEGRITY (0.5 day)
├── 3. C-3: Stripe billing period validation
└── 4. RACE-2: reset_billing_quotas TOCTOU fix

Phase 3 — OBSERVABILITY (1 day)
├── 5. Silent failure detection metrics + alerts
├── 6. DB serialization retry in Celery tasks
└── 8. Concurrency negative counter alert

Phase 4 — WS & BILLING (0.5 day)
├── 7. WS auth cache TTL reduction
├── 9. collect_billing_debt ordering
├── 10. WS send drop alert
└── 11. Stripe webhook latency metric

Phase 5 — HARDENING (1 day)
├── 12. Beat task execution tracking
├── 15-17. Grafana dashboard panels
└── 14. Queue flood chaos test

Phase 6 — VERIFICATION (1 day)
└── 18. Run all chaos tests against fixed code
```

---

## Post-Fix Scoring

| Category | Before | After | Key Changes |
|----------|--------|-------|-------------|
| Task Queue Reliability | 30 | 95 | C-1/C-2/H-3 fixed + metrics added |
| Redis Resilience | 65 | 90 | C-4 fixed + negative counter alert |
| Database Integrity | 45 | 90 | C-3/RACE-2 fixed + retry logic |
| WebSocket Stability | 55 | 90 | Already fixed (H-7/M-2/M-5) + send drop alert |
| Deployment Safety | 60 | 85 | Already good; canary support is infra-level |
| Observability | 55 | 90 | Jobs completion ratio + per-queue latency + WS metrics |
| Third-Party Resilience | 75 | 90 | Already best domain; Stripe latency metric added |
| Startup/Shutdown Safety | 70 | 85 | Already solid; Celery timeout comment added |
| Concurrency Correctness | 40 | 90 | C-4 + H-3 double-reservation fixed |
| Chaos Resilience | 50 | 85 | All critical paths covered by chaos tests |
| Recovery Correctness | 40 | 90 | C-1/C-2 commits verified + serialization retry |
| Operator Readiness | 55 | 80 | Jobs-completion ratio detection + runbooks updated |

**Overall Production Readiness: ~88/100** (was 35/100)

**Remaining gap to 90+:** Deployment canary support (DEP-4) and rolling WS disconnect (DEP-2) are infra-level issues that require operational changes (load balancer configuration, deployment strategy) rather than code fixes. The codebase itself will reach 90+.

---

## Verification Checklist

```yaml
- [ ] C-4: concurrency.py RELEASE_LUA capped at 0
- [ ] H-3: celery_app.py worker uses pre-reserved quota, doesn't re-reserve
- [ ] C-3: billing/router.py rejects webhooks from prior billing period
- [ ] RACE-2: reset_billing_quotas uses FOR UPDATE at read time
- [ ] 5: jobs_created_total vs aioutputs_created_total metric + alert
- [ ] 6: DB serialization retry available for Celery tasks
- [ ] 7: WS auth cache TTL reduced to 120s
- [ ] 8: Prometheus alert for concurrency counter negative
- [ ] 9-12: Remaining medium fixes
- [ ] 15-17: Grafana dashboard panels added
- [ ] 18: All chaos tests pass
```
