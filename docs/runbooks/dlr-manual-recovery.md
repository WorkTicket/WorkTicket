# DLQ Manual Recovery

## Overview
When automated DLQ retry fails, operators can manually re-dispatch dead-lettered jobs.

## Steps

### 1. Identify Stuck Jobs
```sql
SELECT id, job_id, company_id, task_name, error_message, retry_count, created_at
FROM dead_letter_jobs
WHERE last_state NOT IN ('retried', 'max_retries_exceeded')
  AND retry_count < 5
ORDER BY created_at DESC;
```

### 2. Check Original Job State
```sql
SELECT id, ai_processing_state, ai_processing_updated_at
FROM jobs
WHERE id = '<job_id>';
```

Only retry jobs in `failed` or `reserved` state.

### 3. Manual Re-dispatch
```bash
# Via admin endpoint (if available)
curl -X POST https://api.example.com/admin/dlq/retry/<dlq_id> \
  -H "Authorization: Bearer <admin_token>"

# Or trigger via Celery directly
docker compose exec celery-worker-default python -c "
from app.billing.tasks import retry_dead_letter_job
retry_dead_letter_job.delay('<dead_letter_id>')
"
```

### 4. Verify Recovery
```sql
SELECT id, last_state, retry_count, error_message
FROM dead_letter_jobs
WHERE job_id = '<job_id>';
```

Expected: `last_state = 'retried'`, `retry_count` incremented.

### 5. If Still Failing
- Inspect the full error message in the DLQ entry
- Check worker logs for task-level errors
- Check if the original job data (media URLs, etc.) is still accessible
- Consider skipping the job if it's irrecoverable
