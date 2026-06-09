# Silent Job Failure Detection (C-1)

## Symptoms
- Jobs stuck in "processing" state indefinitely
- No AIOutput rows created despite Celery logs showing success
- `rate(workticket_jobs_created_total[5m]) - rate(workticket_jobs_completed_total[5m])` diverges > 0.1

## Root Cause
Missing `await db.commit()` in a Celery task success path. The transaction's changes (AIOutput, UsageLedger, job state) are silently rolled back when the DB connection closes at the end of the task.

## Verification
1. Check the divergence:
   ```
   rate(workticket_jobs_created_total[5m]) - rate(workticket_jobs_completed_total[5m])
   ```
2. If > 0.1 and sustained for > 10 minutes, the SilentJobProcessingFailure alert fires.
3. Check Celery logs for "Failed to commit transaction on success" messages.
4. Check the `process_job_task` function in `celery_app.py` for the `await db.commit()` call in the success path.

## Recovery
1. Identify affected jobs (processing state, no AIOutput):
   ```sql
   SELECT j.id, j.company_id, j.created_at
   FROM jobs j
   LEFT JOIN ai_outputs ao ON ao.job_id = j.id
   WHERE j.ai_processing_state = 'processing'
     AND ao.id IS NULL
     AND j.created_at < NOW() - INTERVAL '10 minutes';
   ```
2. Reset affected job states and re-queue:
   ```python
   await transition_job_state(db, job.id, company_id, AIProcessingState.queued)
   enqueue_job_task(job_id=str(job.id), company_id=str(company_id), ...)
   ```
3. If the missing commit is confirmed, deploy the fix and verify with integration test.

## Prevention
- Verify `await db.commit()` is present in ALL Celery task success paths.
- Monitor the SilentJobProcessingFailure alert.
- Run the chaos test `test_celery_silent_rollback.py` after each deployment.
