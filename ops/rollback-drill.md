# Rollback Drill — Production Readiness Audit Fixes

## Overview

This runbook covers rollback procedures for the 21+ fixes deployed as part of the
production readiness audit (C1-C5, H1-H7, M1-M7). Each fix is independently
reversible, with per-fix risk assessment and verification steps.

## Prerequisites

- Access to deployment environment (Kubernetes `kubectl` or Docker Compose)
- Access to Redis: `redis-cli` or `kubectl exec -it redis-pod -- redis-cli`
- Access to PostgreSQL: `psql` or `kubectl exec -it pg-pod -- psql`
- Previous deployable image tagged (`workticket-backend:previous`)

---

## Drill Steps

### Step 0: Pre-Drill Checks

```bash
# 1. Verify current state is healthy
curl -f https://<host>/healthz
curl -f https://<host>/readyz

# 2. Confirm alerting is working
# Trigger a test alert via /readyz component failure (e.g., stop Redis)

# 3. Record baseline metrics
redis-cli KEYS 'job:lock:*' | wc -l       # Should be 0
redis-cli KEYS 'ws_conn:*' | wc -l        # Active WS connections
redis-cli GET db:circuit:breaker          # Should be nil or open=0
redis-cli ZCARD ws:db_poll_global         # Poll count in current window

# 4. Create a test job to verify normal operation
# (Run the synthetic monitor probe from ops/synthetic_monitor.py)
```

### Step 1: Roll Back Code

```bash
# Option A: Kubernetes — roll back deployment
kubectl rollout undo deployment/workticket-backend
kubectl rollout undo deployment/celery-worker
kubectl rollout undo deployment/celery-beat

# Option B: Docker Compose — redeploy previous image
docker compose stop celery-beat
docker compose stop celery-worker
docker compose up -d backend --image workticket-backend:previous
docker compose up -d celery-worker --image workticket-backend:previous
docker compose up -d celery-beat --image workticket-backend:previous
```

### Step 2: Per-Fix Rollback Verification

| Fix | What to Check | Rollback Command | Verification |
|-----|---------------|-----------------|--------------|
| **C1** (Event loop) | No more `_run_async` | Code revert only | `grep -r "asyncio.run" src/backend/celery_app.py` should show old pattern |
| **C2** (Redis lock) | No `job:lock:*` keys | `redis-cli KEYS 'job:lock:*' \| xargs -r redis-cli DEL` | `redis-cli KEYS 'job:lock:*'` → empty |
| **C3** (R2 delete) | Media DELETE returns 200 without R2 call | Code revert only | Create+delete media, verify R2 object still exists |
| **C4** (WS set) | No `ws_conn:*` keys | `redis-cli KEYS 'ws_conn:*' \| xargs -r redis-cli DEL` | `redis-cli KEYS 'ws_conn:*'` → empty |
| **C5** (Request tracker) | Middleware uses raw inc/dec | Code revert only | Load test with concurrent requests, check counter never negative |
| **H1** (Circuit breaker) | Circuit uses local state only | `redis-cli DEL db:circuit:breaker` | `/healthz` returns DB ok after Redis key deletion |
| **H3** (Compensation) | Compensation deletes partial outputs unconditionally | Code revert only | Force final-retry failure, verify partial outputs deleted |
| **H4** (nowait) | `skip_locked=True` used again | Code revert only | Concurrent webhooks → 400 instead of 409 |
| **H5** (Health pool) | Health check creates own connection | Code revert only | `redis-cli CLIENT LIST | grep healthz` shows new connections on each check |
| **H6** (Beat locks) | No `beat:lock:*` keys | `redis-cli KEYS 'beat:lock:*' \| xargs -r redis-cli DEL` | `redis-cli KEYS 'beat:lock:*'` → empty |
| **H7** (HMAC reject) | Returns instead of `self.reject()` | Code revert only | Send invalid HMAC task → task redelivers infinitely |
| **M1** (Poll limit) | `ws:db_poll_global` cleared | `redis-cli DEL ws:db_poll_global` | `redis-cli EXISTS ws:db_poll_global` → 0 |
| **M2** (Sessionmaker) | New sessionmaker per call | Code revert only | Verify via memory profiling |
| **M3** (Cycle limit) | State cycling not rate limited | Code revert only | Force rapid failed→queued transitions >5/hr, verify they pass |
| **M4** (Reservation) | Jobs stay stuck in reserved | Code revert only | Stale reservation cleanup skips job state reset |
| **M5** (Monotonic) | `time.time()` used in retry guard | Code revert only | NTP step back triggers stale Redis client cache |
| **M6** (Content-length) | No pre-streaming check | Code revert only | Send spoofed content-length → memory allocation |
| **M7** (Idempotency) | Weak company-only check | Code revert only | Same audio URL, different job → second incorrectly skipped |

### Step 3: Post-Rollback Verification

```bash
# 1. Health checks pass
curl -f https://<host>/healthz
curl -f https://<host>/readyz

# 2. Create a test job and verify it completes
python ops/synthetic_monitor.py

# 3. Check no error logs
kubectl logs -l app=workticket-backend --tail=50 | grep -i "error\|critical"

# 4. Verify Redis cleanup
redis-cli DBSIZE   # Should be within normal range
redis-cli KEYS '*' | grep -E "job:lock|beat:lock" | wc -l  # Should be 0

# 5. Check queue depth is normal
kubectl exec -it redis-pod -- redis-cli LLEN default
kubectl exec -it redis-pod -- redis-cli LLEN ai_text
```

### Step 4: Re-apply Fixes (if drill only)

```bash
# 1. Redeploy the fixed version
kubectl rollout undo deployment/workticket-backend  # undo the undo

# 2. Re-create Redis keys if needed
# (Keys auto-populate on first use — no manual creation needed)

# 3. Verify fixes are active
redis-cli KEYS 'job:lock:*'  # Should be empty (locks are ephemeral)
# Run synthetic probe again
python ops/synthetic_monitor.py
```

---

## Success Criteria

| Criterion | Expected | Verification |
|-----------|----------|-------------|
| Zero customer-visible downtime | No 5xx spikes | Grafana dashboard |
| All health endpoints return 200 | `healthz`, `readyz`, `livez` | `curl -f` |
| Synthetic job completes | Job reaches `completed` state | Synthetic monitor exit code 0 |
| No error log spikes | Error rate within baseline | Log analysis dashboard |
| Redis keys cleaned up | No orphaned lock keys | `redis-cli KEYS` check |
| All alerts fire correctly | Expected alerts trigger | Alertmanager UI |

## Risk Matrix

| Fix | Rollback Risk | Customer Impact if Not Rolled Back | Recovery Time |
|-----|---------------|-------------------------------------|---------------|
| C1 | Low | Event loop crash on task retry | 30s (pod restart) |
| C2 | Medium | Double billing on retry race | 5min (fix deploy) |
| C3 | Low | Orphaned R2 storage (cost only) | None (manual cleanup) |
| C4 | Low | WS count underflow, rate limit bypass | 1min (Redis key expiry) |
| H1 | Low | Split-brain DB access during failure | 30s (Lua transaction) |
| H4 | Low | Stripe retry loop on lock conflict | 5min (Stripe auto-retry) |
| H7 | Low | Infinite HMAC redelivery loop | 5min (key rotation) |
