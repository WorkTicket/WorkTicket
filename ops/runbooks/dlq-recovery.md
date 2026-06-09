# DLQ Recovery Runbook

## Detection
- **Alert**: `DeadLetterQueueGrowing` (>10 entries for 5m)
- **Alert**: `DeadLetterWriteFailing` (DB write failures — entries may be lost)
- **Symptom**: Tasks failing and accumulating in dead letter queue

## Query DLQ Entries
```sql
-- View all DLQ entries
SELECT * FROM dead_letter_jobs ORDER BY created_at DESC LIMIT 50;

-- Filter by severity
SELECT * FROM dead_letter_jobs WHERE failure_category = 'stripe_error';
SELECT * FROM dead_letter_jobs WHERE failure_category = 'version_mismatch';

-- Count by category
SELECT failure_category, COUNT(*) FROM dead_letter_jobs GROUP BY failure_category;

-- Entries nearing expiry
SELECT * FROM dead_letter_jobs WHERE expires_at IS NOT NULL AND expires_at < NOW() + INTERVAL '1 day';
```

## Automatic Replay
The `retry_expired_dead_letter_jobs` beat task runs every 5 minutes and replays
entries older than 60 seconds. Entries with `retry_count < max_retries` are
re-enqueued. No manual action needed under normal conditions.

## Manual Replay
To trigger immediate replay:
```python
from celery_app import celery_app
celery_app.send_task('retry_expired_dead_letter_jobs')
```

Or via API:
```bash
curl -X POST http://localhost:8000/api/v1/billing/dlq/replay \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 100}'
```

## When DB Writes Fail (DeadLetterWriteFailing alert)
Before the fix, DLQ entries were written to PID-named JSONL fallback files on
ephemeral storage. This was unreliable (files lost on container restart).

**Now**: If the DB write fails after 3 retries, the entry is **lost** — a
`CRITICAL` log is emitted and the `dlq_write_failures_total` counter is
incremented. There is no JSONL file fallback.

**Actions**:
1. Check DB health — `DatabasePoolSaturation` alert may indicate root cause
2. Inspect worker logs for the `CRITICAL` "Failed to write dead letter entry" message
3. Identify the failed jobs and manually re-trigger if needed:
   ```sql
   SELECT id, company_id, error_message FROM jobs
   WHERE ai_processing_state = 'failed'
   AND updated_at > NOW() - INTERVAL '1 hour';
   ```
4. If DB was transiently unavailable, the next beat cycle will attempt DLQ writes again

## Replay Safety
- Replay uses `(job_id, task_name, failure_category)` dedup — prevents double-processing
- Entries with `version_mismatch` category are skipped (payload format changed)
- `retry_count` is preserved, so replayed tasks start where they left off

## Related
- `ops/runbooks/queue-backup.md` — if replay causes queue backup
- `ops/runbooks/worker-stuck.md` — if workers can't process replays
- `ops/runbooks/redis-oom.md` — if Redis broker is the root cause
