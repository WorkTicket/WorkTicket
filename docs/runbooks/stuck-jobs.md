# Runbook: Stuck AI Jobs

## Symptoms
- `StuckJobsDetected` alert firing
- Customer reports "job stuck at processing/queued"
- Jobs in `reserved`, `running`, or `queued` state beyond timeout

## Timeout Thresholds
| State | Timeout | Auto-Recovery |
|---|---|---|
| `reserved` | 15 min | `cleanup_stale_jobs` beat task marks as failed |
| `processing` | 30 min | `cleanup_stale_jobs` beat task marks as failed |
| `queued` | 60 min | `cleanup_stale_jobs` beat task marks as failed |

## Investigation

### 1. Identify stuck jobs
```sql
SELECT id, company_id, ai_processing_state, ai_processing_updated_at
FROM jobs
WHERE ai_processing_state IN ('queued', 'reserved', 'processing')
  AND ai_processing_updated_at < NOW() - INTERVAL '15 minutes';
```

### 2. Check if auto-recovery is working
Watch the beat task logs:
```
docker compose logs celery-beat | grep cleanup_stale_jobs
```

### 3. C-1/C-2 Silent Failure Detection
If jobs are stuck in processing/queued but Celery logs show success:
- Check `rate(workticket_jobs_created_total[5m]) - rate(workticket_jobs_completed_total[5m])`
- Divergence > 0.1 for > 10min triggers `SilentJobProcessingFailure` alert
- Verify `await db.commit()` exists in process_job_task and scan_for_stalled_ai_jobs
- Check for "Failed to commit transaction on success" in Celery logs

## Recovery Actions

### C-1 Silent Rollback Recovery
```sql
-- Find jobs affected by missing commit
SELECT j.id, j.company_id, j.ai_processing_state
FROM jobs j
LEFT JOIN ai_outputs ao ON ao.job_id = j.id
WHERE j.ai_processing_state IN ('processing', 'reserved')
  AND ao.id IS NULL
  AND j.created_at < NOW() - INTERVAL '10 minutes';
```
Reset and re-queue:
```python
from celery_app import enqueue_job_task
from app.billing.state_machine import transition_job_state, AIProcessingState
await transition_job_state(db, job.id, company_id, AIProcessingState.queued)
enqueue_job_task(job_id=str(job.id), company_id=str(company_id), ...)
```

### C-2 Stalled Job Recovery
The `scan_for_stalled_ai_jobs` beat task (every 5 min) auto-recovers:
- Jobs stuck in `none` state with ai_processed media
- Jobs stuck in `queued` state beyond 5 minutes
- Jobs re-queued > 3 times are transitioned to `failed` and sent to DLQ

### 3. Check worker health
```bash
docker compose ps celery-worker
docker compose logs celery-worker --tail 50
```

### 4. Check queue depth
```bash
redis-cli -a "$REDIS_PASSWORD" LLEN default
redis-cli -a "$REDIS_PASSWORD" LLEN ai_text
redis-cli -a "$REDIS_PASSWORD" LLEN ai_audio
redis-cli -a "$REDIS_PASSWORD" LLEN ai_image
```

### 5. For Redis eviction (zero queue depth but stuck jobs)
→ Run `redis-eviction.md` runbook first

## Manual Recovery

### Re-dispatch a stuck job
```sql
-- Check if AI output exists (job completed but state stuck)
SELECT id FROM ai_outputs WHERE job_id = '<job_id>';

-- If output exists, fix the state manually
UPDATE jobs SET ai_processing_state = 'completed'
WHERE id = '<job_id>';
```

### Force re-dispatch via API
```bash
curl -X POST https://api.workticket.app/api/v1/ai/process-job/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "<job_id>"}'
```

### Clear a poisoned queue
```bash
# Remove specific stuck message
redis-cli -a "$REDIS_PASSWORD" LREM default 0 "<message_content>"
# Purge entire queue (CAREFUL — loses all messages)
redis-cli -a "$REDIS_PASSWORD" DEL default
```

## Prevention
- Monitor queue depth per queue (alert at > 50)
- Monitor worker processing latency (P95 > 60s = warning)
- Ensure `noeviction` on broker Redis
- Keep `CELERY_WORKER_CONCURRENCY=1` to avoid task overlap issues
