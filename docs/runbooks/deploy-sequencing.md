# Deploy Sequencing

## Critical Order

```
1. Stop Celery Beat       → docker compose stop celery-beat
2. Stop Celery Workers    → docker compose stop celery-worker-default celery-worker-text celery-worker-image
3. Deploy API (backend)   → docker compose up -d backend
4. Run DB Migrations      → docker compose exec backend alembic upgrade head
5. Start Celery Workers   → docker compose up -d celery-worker-default celery-worker-text celery-worker-image
6. Start Celery Beat      → docker compose up -d celery-beat
```

## Why This Order

| Step | Rationale |
|------|-----------|
| Stop Beat first | Prevents beat from scheduling tasks old workers can't process |
| Stop Workers | Drains in-flight tasks gracefully (`task_acks_late=True`) |
| Deploy API | New API code is live for HTTP requests |
| Migrate | Schema changes before new workers start |
| Start Workers | Fresh workers with new code |
| Start Beat | Scheduler resumes |

## Version Skew Safety

Tasks carry a `payload_version` field. Workers check compatibility at runtime:
- Old workers reject tasks with `payload_version > MAX_SUPPORTED_VERSION`
- New workers reject tasks with `payload_version < MIN_SUPPORTED_VERSION`
- Rejected tasks return `failure_type: "version_mismatch"` (not sent to DLQ)

## Rollback

```bash
# 1. Tag previous image
docker tag workticket-backend:previous workticket-backend:latest

# 2. Follow deploy sequencing (skip migrate if no schema change)
docker compose stop celery-beat
docker compose stop celery-worker-default celery-worker-text celery-worker-image
docker compose up -d backend
docker compose exec backend alembic downgrade -1  # only if schema changed
docker compose up -d celery-worker-default celery-worker-text celery-worker-image
docker compose up -d celery-beat
```
