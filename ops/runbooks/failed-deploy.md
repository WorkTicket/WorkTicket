# Failed Deploy Runbook

## Detection
- Alert: Sudden increase in 503s or error rate
- Automated: CI/CD pipeline reports health check failure
- Manual: `/readyz` returns degraded status

## Rollback Steps
1. **Stop**: `docker-compose stop backend celery-worker-* celery-beat`
2. **Revert**: `git checkout <previous-stable-tag> -- src/`
3. **Rebuild**: `docker-compose build backend celery-worker-text celery-worker-image celery-worker-audio celery-worker-default celery-worker-beat celery-beat`
4. **Restore DB**: If alembic migration was applied, downgrade:
   ```bash
   docker-compose exec backend alembic downgrade -1
   ```
5. **Start**: `docker-compose up -d backend celery-worker-* celery-beat`
6. **Verify**: Check `/readyz` returns 200

## Verification
- [ ] /readyz returns 200
- [ ] Celery workers ping successfully
- [ ] WebSocket connections accepted
- [ ] Stripe webhooks process correctly
- [ ] No 503 errors in logs
