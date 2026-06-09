# Operator Onboarding: Production-Hardening Runbooks

This guide covers the new runbooks, signals, and procedures introduced by the May 2026 production-hardening sprint.

## New Runbooks

| Runbook | When to Use |
|---------|-------------|
| `redis-oom.md` | Broker Redis OOM / high memory alert |
| `concurrency-drift.md` | Stale concurrency lock keys left behind |
| `worker-stuck.md` | Worker not draining tasks on shutdown |

## New Prometheus Alert Signals

### BrokerRedisMemoryHigh
- **Query**: `workticket_broker_redis_memory_pct > 0.95`
- **Response**: Immediate broker health check; consider Redis failover.
- **New behavior**: Write probe (`SET health:probe EX 2`) added alongside `PING`. Read-only health is no longer enough — a Redis that accepts PING but fails SET (OOM/noeviction) is considered unhealthy.

### ConcurrencyAcquireFailures
- **Query**: `increase(workticket_concurrency_acquire_failures_total[5m]) > 0`
- **Response**: Check Redis availability. Concurrency limiter is now **fail-closed** — when Redis is unreachable, `acquire()` returns `False` and AI processing is blocked until Redis recovers.

### BrokerRedisWriteFailures
- **Query**: `increase(workticket_redis_write_failures_total[5m]) > 0`
- **Response**: Redis is accepting connections but failing writes (OOM, noeviction, or disk full). More dangerous than a total outage because tasks appear to be dispatched but are silently dropped.

### AiOutputDedupHits
- **Query**: `increase(workticket_ai_dedup_hit_total[24h]) > 0`
- **Interpretation**: Duplicate AI job executions were prevented. A non-zero count after deploy is normal for retries. A sudden spike may indicate a retry storm or idempotency key collision.

### WsReauthDbHitsHigh
- **Query**: `rate(workticket_ws_reauth_db_hits[5m]) > 1`
- **Interpretation**: WS reauth is falling through to DB more than once per 5 seconds on average. Usually caused by an auth cache issue or a client reconnecting too frequently.

### WorkerForcedKillsSpiking
- **Query**: `increase(workticket_worker_forced_kill_total[30m]) > 3`
- **Interpretation**: Multiple workers were forcibly killed during shutdown because they didn't drain in time. May indicate stuck tasks or an overly aggressive autoscaler.

## Key Behavioral Changes

### 1. Transaction Split (Fix 1.1)
`_run()` is now three phases:
- **Phase 1** (short-lived DB transaction): load job, transition to reserved/processing, commit, close session.
- **Phase 2** (no DB transaction): AI gateway call, concurrency acquire/release.
- **Phase 3** (new DB transaction): reload job, store output, reconcile billing, commit.

**Operator impact**: If a task fails in Phase 2, Phase 1's work (state transitions, quota reservations) is already committed. The `scan_for_stalled_ai_jobs` beat task will clean up orphaned jobs stuck in "processing" state. Workers no longer hold DB connections for the duration of AI inference.

### 2. Concurrency Fail-Closed (Fix 1.3)
- **Before**: When Redis was unavailable, the concurrency limiter fell back to a local counter, which drifted from the global state.
- **After**: `acquire()` returns `False` when Redis is unreachable. AI processing stops. No drift, but jobs will queue up until Redis recovers.
- **Recovery**: No manual cleanup needed. Once Redis is healthy, `acquire()` starts succeeding again. If stale lock keys remain, use the `concurrency-drift.md` runbook.

### 3. DLQ File Fallback Removed (Fix 1.4)
- **Before**: If the DLQ DB write failed, the entry was written to `/tmp/workticket_dlq_fallback/*.jsonl`. These files were unreliable on ephemeral storage and the replay mechanism was fragile.
- **After**: If the DB write fails after 3 retries, the entry is **lost**. A `dlq_write_failures_total` counter is incremented and a CRITICAL log is emitted.
- **Operator action**: On `dlq_write_failures_total > 0`, check the DB connection pool and disk space. The job that failed to DLQ may need to be manually re-enqueued (see `dlq-recovery.md`).

### 4. Webhook Dedup TTL (Fix 1.6)
- **Before**: TTL=60s. A long-running Stripe webhook handler could process the same event twice.
- **After**: TTL=600s. Covers worst-case handler duration. DB primary key constraint provides secondary dedup.
- **Monitoring**: Use Stripe's dashboard to verify no duplicate charges. The `workticket_stripe_webhook_duplicates_total` metric (if enabled) should stay at 0.

### 5. Broker Health Write Probe (Fix 2.2)
`is_broker_healthy()` now does:
1. `r.ping()` — connection-level check
2. `r.set("health:probe", "1", ex=2)` — write probe (detects OOM/noeviction)
3. `r.info("memory")` — memory usage check (>80% fires a warning + gauge)

If write probe fails, broker is considered unhealthy. Task dispatch is blocked if unhealthy > 60s.

## Training Checklist

- [ ] Read all 3 new/updated runbooks (redis-oom, concurrency-drift, worker-stuck)
- [ ] Know the 6 new Prometheus alert rules and their runbook links
- [ ] Practice simulating a broker Redis OOM: block writes, verify write probe detection, verify task dispatch stops
- [ ] Practice simulating a Redis outage: verify concurrency fails closed, verify beat tasks skip gracefully
- [ ] Practice recovering from concurrency drift: run `concurrency-drift.md` cleanup procedure
- [ ] Understand the transaction split: know that Phase 1 work survives a Phase 2 crash
- [ ] Know how to manually re-enqueue a job when DLQ write fails (see `dlq-recovery.md`)
- [ ] Run `chaos/run_all.py` in staging and understand each test's purpose
- [ ] Review Grafana `workticket-overview` dashboard — know where each new panel lives
