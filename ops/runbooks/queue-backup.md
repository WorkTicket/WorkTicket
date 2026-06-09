# Queue Backup Runbook

## Symptoms
- `workticket_queue_depth > 400` alert
- Task processing latency > 60s
- Backpressure 429 errors from enqueue endpoint

## Detection
```bash
# Check queue depths
redis-cli LLEN default
redis-cli LLEN ai_text
redis-cli LLEN ai_audio
redis-cli LLEN ai_image
redis-cli LLEN beat

# Check worker load
celery -A celery_app inspect active
```

## Steps

1. **Identify cause**
   - Check if AI backend is healthy: `curl http://ollama:11434/api/tags`
   - Check if Redis is healthy: `redis-cli PING`
   - Check if DB is healthy: `psql -c "SELECT 1"`

2. **Temporarily increase worker count**
   ```bash
   docker compose up -d --scale celery-worker=3 celery-worker
   ```

3. **Rate-limit enqueue**
   ```bash
   celery -A celery_app control rate_limit ai_text 30/m
   celery -A celery_app control rate_limit ai_audio 20/m
   ```

4. **Clear specific queue if stuck**
   ```bash
   # Inspect queue contents
   redis-cli LRANGE default 0 10
   
   # Purge queue (LAST RESORT)
   celery -A celery_app purge -Q ai_image
   ```

## Prevention
- Proactive backpressure at 80% queue depth
- Per-queue thresholds: default=500, ai_text=200, ai_audio=200, ai_image=200, beat=50
- Monitor queue growth trends
