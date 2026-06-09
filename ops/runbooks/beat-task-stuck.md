# Beat Task Stuck Runbook

## Detection
- Alert: `BeatLockTTLNotRenewed` or billing reconciliation not running
- Symptom: Quotas not resetting, debt not collecting, stale jobs accumulating

## Triage
1. Check Redis beat locks: `redis-cli KEYS "beat:lock:*"`
2. Check lock TTLs: `redis-cli TTL beat:lock:<task_name>`
3. Check reconciliation lock: `redis-cli TTL lock:billing:reconciliation`

## Force-Release Redis Lock
```bash
redis-cli DEL beat:lock:reset_billing_quotas
redis-cli DEL beat:lock:collect_billing_debt
redis-cli DEL lock:billing:reconciliation
```

## Manual Execution
If the beat task is stuck and needs manual execution:
1. Release the lock as above
2. Trigger the task via Celery:
   ```python
   from celery_app import celery_app
   celery_app.send_task('reset_billing_quotas')
   ```
3. Monitor execution in Celery logs

## Prevention
- Renewable beat lock with heartbeat TTL extension
- Lock contention metrics alert before tasks get stuck
- Avoid long-running beat tasks that exceed lock TTL
