# Blue/Green Deployment Strategy

## Overview

Blue/green deployment minimizes downtime by maintaining two identical
production environments (blue = active, green = idle). New code is
deployed to the idle environment, validated, and then traffic is
switched over.

The two environments share the same database and message broker
(Redis). Only the application layer is duplicated. This means database
migrations on green must be backward-compatible with the blue
application code still running in production until the switch.

## Environments

| Environment | Purpose | URL Pattern |
|-------------|---------|-------------|
| **Blue** | Currently serving production traffic | `app.workticket.com` |
| **Green** | Staged with new release | `green.workticket.com` |

## Docker Compose Service Duplication Strategy

Blue and green run simultaneously using a single `docker-compose`
project with service name suffixes. Each service is duplicated with a
`-blue` or `-green` suffix and assigned separate host ports so both
stacks can coexist on the same host.

### Key Principles

- **Shared services** (database, Redis, PgBouncer) are NOT duplicated.
  They are defined once and both blue and green connect to them.
- **Application services** (backend, celery-worker, celery-beat) are
  duplicated with `-blue` and `-green` suffixes.
- **Port mappings** differ: blue backend uses host port `8000`, green uses
  host port `8001`. Blue celery-flower uses `5555`, green uses `5556`.
- **Container names** and **network aliases** include the colour suffix
  so service discovery works within each colour group.

### Example: docker-compose.blue-green.yml

```yaml
version: "3.9"

x-common-backend: &common-backend
  image: ${WORKTICKET_BACKEND_IMAGE:-workticket/backend:latest}
  env_file: .env.production
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  environment:
    SHUTDOWN_GRACE_SECONDS: "240"

services:
  # -------------------------------------------------------------------
  # Shared infrastructure (NOT duplicated)
  # -------------------------------------------------------------------
  postgres:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: workticket
      POSTGRES_USER: workticket
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U workticket"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  pgbouncer:
    image: edoburu/pgbouncer:latest
    environment:
      DB_HOST: postgres
      DB_USER: workticket
      DB_PASSWORD: ${DB_PASSWORD}
    depends_on:
      - postgres

  # -------------------------------------------------------------------
  # Nginx — single entry point; config determines upstream colour
  # -------------------------------------------------------------------
  nginx:
    image: nginx:stable-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d/blue.conf:/etc/nginx/conf.d/blue.conf:ro
      - ./nginx/conf.d/green.conf:/etc/nginx/conf.d/green.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend-blue
      - backend-green

  # -------------------------------------------------------------------
  # BLUE — active production
  # -------------------------------------------------------------------
  backend-blue:
    <<: *common-backend
    container_name: workticket-backend-blue
    ports:
      - "8000:8000"
    networks:
      default:
        aliases:
          - backend-blue

  celery-worker-blue:
    image: ${WORKTICKET_BACKEND_IMAGE:-workticket/backend:latest}
    container_name: workticket-celery-worker-blue
    command: celery -A celery_app worker -Q default,ai_text,ai_audio,ai_image
    env_file: .env.production
    environment:
      WORKTICKET_COLOR: blue
      SHUTDOWN_GRACE_SECONDS: "240"
    restart: unless-stopped
    depends_on:
      - redis
      - postgres

  celery-beat-blue:
    image: ${WORKTICKET_BACKEND_IMAGE:-workticket/backend:latest}
    container_name: workticket-celery-beat-blue
    command: celery -A celery_app beat
    env_file: .env.production
    environment:
      WORKTICKET_COLOR: blue
    restart: unless-stopped
    depends_on:
      - redis
      - postgres

  flower-blue:
    image: mher/flower:2.0
    container_name: workticket-flower-blue
    command: celery flower --broker=redis://redis:6379/0
    ports:
      - "5555:5555"
    depends_on:
      - redis

  # -------------------------------------------------------------------
  # GREEN — staged release
  # -------------------------------------------------------------------
  backend-green:
    <<: *common-backend
    container_name: workticket-backend-green
    ports:
      - "8001:8000"
    networks:
      default:
        aliases:
          - backend-green

  celery-worker-green:
    image: ${WORKTICKET_BACKEND_IMAGE:-workticket/backend:latest}
    container_name: workticket-celery-worker-green
    command: celery -A celery_app worker -Q default,ai_text,ai_audio,ai_image
    env_file: .env.production
    environment:
      WORKTICKET_COLOR: green
      SHUTDOWN_GRACE_SECONDS: "240"
    restart: unless-stopped
    depends_on:
      - redis
      - postgres

  celery-beat-green:
    image: ${WORKTICKET_BACKEND_IMAGE:-workticket/backend:latest}
    container_name: workticket-celery-beat-green
    command: celery -A celery_app beat
    env_file: .env.production
    environment:
      WORKTICKET_COLOR: green
    restart: unless-stopped
    depends_on:
      - redis
      - postgres

  flower-green:
    image: mher/flower:2.0
    container_name: workticket-flower-green
    command: celery flower --broker=redis://redis:6379/0
    ports:
      - "5556:5555"
    depends_on:
      - redis

volumes:
  pgdata:
```

### Nginx Upstream Switching

Nginx uses an include-based approach. The active colour is controlled
by which upstream configuration file is symlinked or included:

**nginx/conf.d/blue.conf** (upstream targeting blue):
```nginx
upstream workticket_backend {
    server backend-blue:8000 max_fails=3 fail_timeout=30s;
}
```

**nginx/conf.d/green.conf** (upstream targeting green):
```nginx
upstream workticket_backend {
    server backend-green:8000 max_fails=3 fail_timeout=30s;
}
```

Switching traffic is a config swap followed by an nginx reload:

```bash
# Switch to green
cp nginx/conf.d/green.conf nginx/conf.d/active-upstream.conf
docker compose exec nginx nginx -s reload

# Switch back to blue (rollback)
cp nginx/conf.d/blue.conf nginx/conf.d/active-upstream.conf
docker compose exec nginx nginx -s reload
```

## Pre-Deploy Checklist

Run through these checks before starting the deploy to green:

- [ ] **CI/CD all green**: All tests, lint, and type checks passed on the release commit.
- [ ] **DB migration review**: Inspected `alembic/versions/` for the release. Migration
      is backward-compatible (no DROP column, no RENAME that blues' code depends on).
- [ ] **Migration dry-run**: Ran `alembic upgrade head --sql` and reviewed the output.
- [ ] **Configuration diff**: Compared `.env.production` between blue and the release.
      No breaking config changes (new required vars are set).
- [ ] **Resource headroom**: Host has enough CPU, memory, and disk to run both stacks
      simultaneously (check `docker stats`, `df -h`).
- [ ] **Port availability**: Ports 8001 and 5556 are available on the host.
- [ ] **Broker memory**: Redis maxmemory is below 70% (`redis-cli INFO memory`).
- [ ] **DB connection pool**: PgBouncer has capacity for green's additional connections.
- [ ] **Nginx configs ready**: Both `blue.conf` and `green.conf` exist and pass
      `nginx -t` validation.
- [ ] **Rollback plan documented**: Team knows the rollback trigger criteria and commands.
- [ ] **Monitoring dashboards ready**: Grafana dashboards opened for both blue and green
      metrics (filtered by `WORKTICKET_COLOR` label).

## Detailed Health-Gate Steps

Before traffic switch, every gate must pass. Run these in order:

### Step 1: Migration Dry-Run on Green

```bash
# Start green database (shared) but only run migration SQL preview
docker compose -f docker-compose.blue-green.yml exec backend-green \
  alembic upgrade head --sql

# Review the output. Ensure no destructive operations
# (DROP TABLE, DROP COLUMN, ALTER COLUMN ... TYPE that would break blue).
```

### Step 2: Deploy Green Stack

```bash
# Pull/build green image with the new release tag
export WORKTICKET_BACKEND_IMAGE=workticket/backend:v2.0.0

# Start only the green application services
docker compose -f docker-compose.blue-green.yml up -d \
  backend-green celery-worker-green celery-beat-green flower-green

# Run the actual migration on green
docker compose -f docker-compose.blue-green.yml exec backend-green \
  alembic upgrade head
```

### Step 3: Run Smoke Tests Against Green

```bash
# Basic health endpoints
curl -fsS http://localhost:8001/livez
curl -fsS http://localhost:8001/healthz
curl -fsS http://localhost:8001/readyz
curl -fsS http://localhost:8001/beta-gate

# Full smoke test suite against green
pytest tests/smoke/ --base-url http://localhost:8001 -v

# Verify SLO metrics are emitting
curl -s http://localhost:8001/api/v1/slo | python -m json.tool
```

### Step 4: Switch Traffic

```bash
# Method A: Automated PowerShell script
.\ops\scripts\blue-green-switch.ps1 -TargetColor green -ApiPort 8001

# Method B: Manual swap
cp nginx/conf.d/green.conf nginx/conf.d/active-upstream.conf
docker compose -f docker-compose.blue-green.yml exec nginx nginx -s reload

# Verify traffic is hitting green
for i in 1 2 3; do
  curl -s https://app.workticket.com/healthz | grep -q '"color":"green"' && echo "OK"
  sleep 1
done
```

### Step 5: Monitor Green for 5 Minutes

```bash
# Monitor every 10 seconds for 5 minutes (30 iterations)
for i in $(seq 1 30); do
  echo "=== Check $i/30 at $(date -u +%H:%M:%SZ) ==="
  curl -fsS -o /dev/null -w "  livez:  %{http_code}\n" https://app.workticket.com/livez
  curl -fsS -o /dev/null -w "  healthz: %{http_code}\n" https://app.workticket.com/healthz
  curl -fsS -o /dev/null -w "  readyz: %{http_code}\n" https://app.workticket.com/readyz

  # Check error rate
  curl -s https://app.workticket.com/api/v1/slo | python -c \
    "import sys,json; d=json.load(sys.stdin); print(f'  SLO avail: {d.get(\"availability\",0):.4f}')"

  # Check worker health
  docker compose -f docker-compose.blue-green.yml exec celery-beat-green \
    celery -A celery_app inspect ping --timeout 5 2>&1 | grep -q pong && echo "  workers: OK" || echo "  workers: FAIL"

  sleep 10
done
```

### Step 6: Drain and Remove Blue

After confirming green is stable (5+ minutes of clean monitoring), drain
blue gracefully and remove its containers.

```bash
# 1. Stop accepting new tasks on blue Celery workers
docker compose -f docker-compose.blue-green.yml stop celery-beat-blue

# 2. Wait for running tasks to complete (max 240s)
.\ops\scripts\drain-connections.ps1 -Service celery -Timeout 240 -Force

# 3. Stop and remove blue application containers
docker compose -f docker-compose.blue-green.yml stop backend-blue
docker compose -f docker-compose.blue-green.yml rm -f \
  backend-blue celery-worker-blue celery-beat-blue flower-blue

# 4. Green is now sole production — blue is now the idle slot for
#    the next deploy
```

## Rollback Procedure

### Keep-Blue Window

After traffic is switched to green, **keep blue running for at least 10
minutes**. Do not remove blue containers until the monitoring window
(Step 5) completes cleanly and you are confident in the green release.

### Instant Rollback: Nginx Swap

If problems are detected during the monitoring window, roll back
immediately by pointing nginx back to blue:

```bash
# Automated
.\ops\scripts\blue-green-switch.ps1 -TargetColor blue

# Manual
cp nginx/conf.d/blue.conf nginx/conf.d/active-upstream.conf
docker compose -f docker-compose.blue-green.yml exec nginx nginx -s reload
```

This takes effect within seconds — nginx reload is non-blocking and
existing connections to green are allowed to drain naturally.

### Database Schema Rollback

If the deployment included a schema migration that must be reversed:

```bash
# Run downgrade on green only (blue code was already compatible
# since we only run backward-compatible migrations)
docker compose -f docker-compose.blue-green.yml exec backend-green \
  alembic downgrade -1

# If multiple migrations were applied in this release:
docker compose -f docker-compose.blue-green.yml exec backend-green \
  alembic downgrade <target-revision>
```

### Data Rollback Considerations

Since blue and green share the same database:

- **New data written to green** (after the traffic switch) persists in the
  database after rollback. The schema rollback only reverses DDL, not DML.
- **If the migration added a NOT NULL column** to an existing table, those
  rows may now have data in that column. Rolling back the migration (DROP
  COLUMN) will lose this data.
- **Mitigation**: Always design migrations to be backward-compatible. Add
  nullable columns with defaults, then backfill, then add NOT NULL in a
  *separate* migration after the switch is finalized.
- **Celery tasks enqueued during green's window** remain in Redis. If the
  task signatures changed between versions, drain the queue before
  rollback:
  ```bash
  docker compose -f docker-compose.blue-green.yml exec celery-beat-green \
    celery -A celery_app purge -f
  ```

## Connection Draining

Graceful connection draining ensures no in-flight requests are dropped
during a switch or decommission.

### Nginx Graceful Shutdown

Configure in `nginx.conf`:

```nginx
worker_shutdown_timeout 240s;
```

When nginx receives SIGQUIT, it:
1. Stops accepting new connections.
2. Waits up to `worker_shutdown_timeout` for active connections to
   complete.
3. Force-closes any connections still open after the timeout.

For reloads (`nginx -s reload`), old worker processes follow this
same graceful shutdown path while new workers pick up traffic
immediately.

### Backend Graceful Shutdown

Set via environment variable (already in the compose file above):

```yaml
environment:
  SHUTDOWN_GRACE_SECONDS: "240"
```

The backend (Uvicorn) handles SIGTERM by:
1. Stopping the accept loop (no new connections).
2. Waiting up to `SHUTDOWN_GRACE_SECONDS` for in-flight requests to
   complete.
3. Closing keep-alive connections.

### Celery Worker Graceful Termination

Celery workers respond to SIGTERM with a controlled shutdown:

```bash
# Send SIGTERM (graceful)
docker compose -f docker-compose.blue-green.yml kill -s SIGTERM celery-worker-blue

# Worker will:
# 1. Stop consuming new tasks from the broker.
# 2. Complete currently running tasks (up to task_soft_time_limit).
# 3. Re-queue any prefetched but unstarted tasks.
# 4. Exit.

# Monitor shutdown progress
docker compose -f docker-compose.blue-green.yml logs -f celery-worker-blue
```

If workers need to be force-stopped after the grace period:

```bash
# Send SIGKILL only after graceful timeout expires
docker compose -f docker-compose.blue-green.yml kill -s SIGKILL celery-worker-blue
```

The drain script at `ops/scripts/drain-connections.ps1` can automate
this for all celery services in the fading colour.

## Post-Deploy Validation

After the monitoring window passes and green is confirmed stable, run
the full validation suite:

```bash
# Run the post-deploy validation script against production
.\ops\scripts\post-deploy-validation.ps1 `
  -PrometheusUrl "http://prometheus.prod:9090" `
  -ApiBaseUrl "https://app.workticket.com" `
  -GrafanaUrl "https://grafana.workticket.com"
```

### Manual Validation Checklist

- [ ] **All health endpoints return OK**: `/livez`, `/healthz`, `/readyz`,
      `/beta-gate` all 200.
- [ ] **SLO metrics within threshold**: Availability > 0.999, p95 latency
      < 500ms.
- [ ] **Celery workers healthy**: `celery inspect ping` returns pong from
      all workers.
- [ ] **No spike in 5xx errors**: Compare Grafana error rate panel for
      the 5 minutes before and after switch.
- [ ] **DB connection pool stable**: Pool utilization < 80% on PgBouncer.
- [ ] **Redis memory stable**: No anomalous growth after switch.
- [ ] **WebSocket connections migrated**: Clients reconnected cleanly
      (check `workticket_ws_connections_total`).
- [ ] **Stripe webhooks received**: Verify at least one webhook event
      processed in the last 2 minutes.
- [ ] **Celery beat schedule intact**: No missed scheduled tasks
      (check `workticket_beat_schedule_miss_total`).
- [ ] **All smoke tests pass**: Re-run smoke suite against production.

### Go/No-Go Decision

| Criterion | GO | NO-GO |
|-----------|----|-------|
| Health endpoints | All 200 | Any non-200 |
| 5xx error rate | < 0.1% increase | >= 0.1% increase |
| SLO availability | > 0.999 | <= 0.999 |
| Celery workers | All pong | Any worker missing |
| Smoke tests | 100% pass | Any failure |

If any NO-GO criterion is met, execute the rollback procedure
immediately.
