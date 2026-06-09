# Rolling Restart Runbook

Zero-downtime deployment procedure for WorkTicket backend services.

## Prerequisites

- Docker Compose v2.20+
- Load balancer with health check probes (`/livez`, `/healthz`, `/readyz`)
- Redis HA (sentinel) or replication configured
- PgBouncer in transaction-pooling mode
- At least 2 replicas of each service behind the load balancer

## 1. Pre-Deployment Verification

```bash
# 1. Verify cluster health
curl -sf http://localhost:8000/readyz | jq .
curl -sf http://localhost:8000/beta-gate | jq .

# 2. Check Celery worker health
celery -A celery_app inspect ping --timeout 5

# 3. Verify Redis connectivity
redis-cli -a "$REDIS_PASSWORD" ping

# 4. Check database connections (pgbouncer)
psql -h pgbouncer -c "SHOW POOLS;"

# 5. Verify backup is fresh
# (check latest WAL archive timestamp in R2/S3)
```

## 2. Drain Connection Pool (Celery Workers)

Before restarting any Celery worker, drain its active connections:

```bash
# Drain specific worker queues
python ops/scripts/drain-connections.py --queue ai_text   --timeout 60
python ops/scripts/drain-connections.py --queue ai_audio  --timeout 60
python ops/scripts/drain-connections.py --queue ai_image  --timeout 60
python ops/scripts/drain-connections.py --queue default   --timeout 60
```

## 3. Rolling Restart Sequence

### Step 1: Update backend API (FastAPI)

```bash
# Pull new image
docker compose pull backend

# Rolling restart one replica at a time
docker compose up -d --scale backend=2 --no-recreate backend
# Wait for /readyz on new replica
for i in 1 2 3; do
    if curl -sf http://localhost:8000/readyz 2>/dev/null; then
        break
    fi
    sleep 2
done

# Scale down old
docker compose up -d --scale backend=1 --no-recreate backend
sleep 5

# Scale back up
docker compose up -d --scale backend=2 --no-recreate backend
```

### Step 2: Migrate database

```bash
# Run pending migrations (non-blocking if using pgbouncer transaction mode)
docker compose exec -T backend alembic upgrade head

# Verify migration
docker compose exec -T backend alembic current
```

### Step 3: Update Celery workers

```bash
# Restart beat first (only one instance, brief downtime acceptable)
docker compose up -d --force-recreate celery-beat
sleep 10

# Rolling restart worker pools
for queue in default ai_text ai_audio ai_image; do
    echo "Restarting $queue workers..."
    docker compose up -d --scale "celery-worker-$queue=0" --no-recreate "celery-worker-$queue"
    sleep 5
    docker compose up -d --scale "celery-worker-$queue=2" --no-recreate "celery-worker-$queue"
    # Wait for worker registration
    celery -A celery_app inspect ping --timeout 10 --destination "celery@$queue"
    sleep 10
done
```

### Step 4: Update supporting services

```bash
# Restart Redis (only if HA mode -- brief failover expected)
docker compose up -d --force-recreate redis-broker

# Restart PgBouncer (connection drain handled by pgbouncer reconnect)
docker compose up -d --force-recreate pgbouncer
```

## 4. Post-Deployment Verification

```bash
# 1. Health endpoints
curl -sf http://localhost:8000/livez    | jq .
curl -sf http://localhost:8000/healthz  | jq .
curl -sf http://localhost:8000/readyz   | jq .

# 2. Verify Celery workers registered
celery -A celery_app inspect registered --timeout 5

# 3. Check queue depths (should be processing normally)
for q in ai_text ai_audio ai_image default beat; do
    echo "Queue $q:"
    celery -A celery_app inspect active_queues --timeout 3 | grep -A1 "$q"
done

# 4. Run billing parity check
python ops/scripts/fix_ghost_reservations.py --dry-run

# 5. Synthetic probe (end-to-end)
python ops/synthetic_monitor.py --check-quota --check-ai --check-websocket
```

## 5. Rollback Procedure

If the deployment fails health checks or causes elevated error rates:

```bash
# Quick rollback to previous tag
export PREVIOUS_TAG=v1.0.0-beta.9
docker compose pull backend
docker compose up -d --force-recreate backend

# Rollback database migration (if schema changed)
docker compose exec -T backend alembic downgrade -1

# Restart Celery workers with previous image
docker compose up -d --force-recreate celery-beat
for queue in default ai_text ai_audio ai_image; do
    docker compose up -d --force-recreate "celery-worker-$queue"
    sleep 10
done

# Verify rollback
curl -sf http://localhost:8000/readyz | jq .
```

> **Note**: If using `ops/scripts/rollback.ps1` or `rollback.sh`, those scripts automate this procedure. See `ops/scripts/rollback.md` for details.

## 6. Monitoring During Restart

During the rolling restart, watch for:

| Signal | Action |
|--------|--------|
| 503 responses > 5% of requests | Pause deployment, investigate backend health |
| Queue depth growing > 2x baseline | Reduce concurrency, allow workers to catch up |
| Redis replication lag > 10s | Wait for replication before proceeding |
| PgBouncer pool exhaustion | Reduce `db_pool_size` temporarily |
| Circuit breaker opening (Stripe, AI) | Hold deployment, investigate upstream health |
| Worker crash loops | Inspect `detect_worker_crash_loops` metric, roll back if critical |

## 7. Emergency Stop

```bash
# Stop all new traffic at load balancer
# (cloud-specific: update LB target group health check to /livez returns 503)

# Force-stop all restart operations
# Scale everything back to original state
docker compose up -d --scale backend=3 --scale celery-worker-default=2 \
    --scale celery-worker-ai_text=2 --scale celery-worker-ai_audio=2 \
    --scale celery-worker-ai_image=2
```
