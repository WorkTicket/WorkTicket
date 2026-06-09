# Runbook: Celery Scaling

## Architecture
- Separate worker containers per queue (`ai_text`, `ai_audio`, `ai_image`, `default`)
- Each worker runs with `-c 1` (single thread) due to async event loop limitation
- Scale by adding container replicas, NOT by increasing concurrency

## Detecting Backlog
- Metric: `celery_task_queue_depth` per queue
- Inspect: `celery -A celery_app inspect active`
- Inspect: `celery -A celery_app inspect reserved`

## Scaling Up
```bash
docker-compose up -d --scale celery-worker-text=3
docker-compose up -d --scale celery-worker-audio=2
```

## Dead Letter Queue
- Failed jobs go to `dead_letter_jobs` table
- Retry: `python scripts/retry_dlq.py`
- Manual: UPDATE dead_letter_jobs SET last_state='queued'
