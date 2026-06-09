# Failed Deploy Rollback Runbook

## Symptoms
- Health check failures after deployment
- Increased error rates in new version
- Database migration issues
- Celery task processing failures

## Steps

### 1. Identify the deployed version
```bash
# Check current deploy ID
kubectl get deployment workticket-api -o jsonpath='{.spec.template.metadata.labels.deploy-id}'
# Or for docker-compose:
docker-compose ps
```

### 2. Verify DB schema compatibility
Before rolling back, check that the rollback target's schema is compatible:
```bash
# Check current migration level
alembic current
# Check what migrations would be reverted
alembic history
```

### 3. Drain queues before rollback (if time permits)
```bash
# Stop accepting new tasks
# Scale API to 0 to stop new job submissions
# Let workers finish current tasks
celery -A celery_app inspect active
```

### 4. Roll back the deployment
**Kubernetes:**
```bash
kubectl rollout undo deployment/workticket-api
kubectl rollout undo deployment/celery-worker
kubectl rollout undo deployment/celery-beat
```

**Docker Compose:**
```bash
# Revert to previous image tag
git checkout <previous-stable-tag>
docker-compose up -d --build
```

### 5. Roll back DB migration (if needed)
```bash
# Downgrade by 1 revision
alembic downgrade -1
# Or downgrade to a specific revision
alembic downgrade <revision_id>
```

### 6. Verify recovery
- Check `/healthz` returns 200
- Check `/readyz` shows all components "ok"
- Verify Celery workers are processing tasks
- Monitor error rates in logs
- Run a test job end-to-end

### 7. Post-mortem
- Identify root cause of deployment failure
- Update deployment checklist
- Add automated preflight checks
