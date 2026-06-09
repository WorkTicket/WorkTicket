# Queue Backlog Runbook

## Symptoms
- `CeleryQueueGrowing` alert
- `workticket_celery_queue_depth_total > 50`
- Users reporting slow AI processing
- Jobs stuck in `queued` state for extended periods

## Steps

### 1. Inspect queue depth per type
Access `/readyz` endpoint to see per-queue depths:
```json
"celery": {
  "queue_depth": {
    "default": 5,
    "ai_text": 45,
    "ai_audio": 12,
    "ai_image": 3
  }
}
```

Or query Redis directly:
```bash
redis-cli -h <host> LLEN default
redis-cli -h <host> LLEN ai_text
redis-cli -h <host> LLEN ai_audio
redis-cli -h <host> LLEN ai_image
```

### 2. Check worker health
```bash
celery -A celery_app inspect ping
celery -A celery_app inspect active
celery -A celery_app inspect reserved
```

### 3. Scale workers temporarily
Increase worker replicas in docker-compose:
```yaml
# Scale specific queue consumers
celery-worker-ai-text:
  deploy:
    replicas: 3
```

Or restart workers with higher concurrency:
```bash
docker-compose up -d --scale celery-worker-default=3 --scale celery-worker-ai-text=5
```

### 4. Check for stuck tasks
If tasks are reserved but not executing, workers may be stuck:
```bash
celery -A celery_app inspect active
# Revoke stuck tasks if needed
celery -A celery_app control revoke <task_id> --terminate
```

### 5. Purge a queue (LAST RESORT — data loss risk)
```bash
# Remove all messages from a specific queue
redis-cli -h <host> DEL ai_text
# Or via Celery
celery -A celery_app purge -Q ai_text -f
```

### 6. Verify recovery
- Queue depth returns to normal levels
- Jobs transition to `completed` state
- No new backlog accumulation
