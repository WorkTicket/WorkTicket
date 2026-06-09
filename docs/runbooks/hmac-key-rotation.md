# HMAC Key Rotation Runbook

## Overview

Celery tasks are signed with `CELERY_TASK_SIGNING_KEY`. Key rotation requires coordinating key rollout across all workers and beat processes.

## Rotation Procedure

1. **Set new key on all workers** by updating environment variable `CELERY_TASK_SIGNING_KEY` and restarting each worker:
   - `celery-worker-default`
   - `celery-worker-text`
   - `celery-worker-image`
   - `celery-worker-audio`
   - `celery-worker-beat`

2. **Sequence:**
   ```
   Stop Beat → Stop Workers → Deploy → Migrate → Start Workers → Start Beat
   ```

3. **Verification:**
   - Check `workticket_unsigned_task_rejected_total` remains 0
   - Check `workticket_beat_lock_skipped_total` remains 0
   - Monitor DLQ for `version_mismatch` or `security` failure categories

4. **Rollback:**
   - Redeploy old key env var
   - Restart all workers
   - Tasks signed with old key will be accepted as long as they haven't expired from the queue

## Atomic Key Rotation

For zero-downtime rotation:
1. Set OLD key as `CELERY_TASK_SIGNING_KEY` on all workers
2. Deploy code with dual-key verification (old + new)
3. Rotate to NEW key
4. Deploy code removing old key verification
