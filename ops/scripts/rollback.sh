#!/usr/bin/env bash
#
# rollback.sh — Rollback WorkTicket deployment to a previous version.
#
# Usage:
#   ./rollback.sh v1.0.0-beta.9                   # basic rollback
#   ./rollback.sh v1.0.0-beta.9 --rollback-migrate # also downgrade DB
#   ./rollback.sh v1.0.0-beta.9 --dry-run          # dry run
#   ./rollback.sh v1.0.0-beta.9 --skip-workers     # skip worker restart
#
# Requirements:
#   - docker compose v2.20+
#   - curl, jq
#   - Access to the target Docker image

set -euo pipefail

TARGET_VERSION="${1:?Usage: $0 <target-version> [--rollback-migrate] [--dry-run] [--skip-workers]}"
ROLLBACK_MIGRATE=false
DRY_RUN=false
SKIP_WORKERS=false

for arg in "$@"; do
    case "$arg" in
        --rollback-migrate) ROLLBACK_MIGRATE=true ;;
        --dry-run)          DRY_RUN=true ;;
        --skip-workers)     SKIP_WORKERS=true ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/../../src" && pwd)"

log()  { echo -e "\033[32m[$(date +%T)] $*\033[0m"; }
warn() { echo -e "\033[33m[$(date +%T)] $*\033[0m"; }
err()  { echo -e "\033[31m[$(date +%T)] $*\033[0m" >&2; }

log "=== WorkTicket Rollback to $TARGET_VERSION ==="
log "Compose directory: $COMPOSE_DIR"
$DRY_RUN && warn "=== DRY RUN MODE ==="

cd "$COMPOSE_DIR"

# ------------------------------------------------------------------
# 1. Verify target version exists
# ------------------------------------------------------------------
log "[1/6] Verifying image workticket-backend:$TARGET_VERSION..."
if ! $DRY_RUN; then
    if ! docker image inspect "workticket-backend:$TARGET_VERSION" &>/dev/null; then
        warn "Image not found locally. Attempting pull..."
        docker pull "workticket-backend:$TARGET_VERSION" || {
            err "Failed to pull image. Aborting."
            exit 1
        }
    fi
fi

# ------------------------------------------------------------------
# 2. Drain active tasks
# ------------------------------------------------------------------
log "[2/6] Draining Celery queues..."
if ! $DRY_RUN; then
    docker compose exec -T celery-beat \
        celery -A celery_app control cancel_feed 2>/dev/null || true
fi

# ------------------------------------------------------------------
# 3. Rollback API backend
# ------------------------------------------------------------------
log "[3/6] Rolling back API backend..."
if ! $DRY_RUN; then
    export WORKTICKET_BACKEND_TAG="$TARGET_VERSION"
    docker compose up -d --force-recreate backend
    log "Waiting for backend to be ready..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8000/readyz &>/dev/null; then
            log "Backend is healthy."
            break
        fi
        sleep 2
    done
    if ! curl -sf http://localhost:8000/readyz &>/dev/null; then
        err "Backend did not become healthy within 60s. Check logs: docker compose logs backend"
        exit 1
    fi
fi

# ------------------------------------------------------------------
# 4. Rollback database migration
# ------------------------------------------------------------------
if $ROLLBACK_MIGRATE; then
    log "[4/6] Rolling back database migration..."
    if ! $DRY_RUN; then
        docker compose exec -T backend alembic downgrade -1 || {
            err "Database migration rollback failed."
            exit 1
        }
        log "Database migration rolled back."
    fi
else
    log "[4/6] Skipping DB migration rollback (use --rollback-migrate)"
fi

# ------------------------------------------------------------------
# 5. Restart Celery workers
# ------------------------------------------------------------------
if ! $SKIP_WORKERS; then
    log "[5/6] Restarting Celery workers..."
    for svc in celery-beat celery-worker-default celery-worker-ai_text \
               celery-worker-ai_audio celery-worker-ai_image; do
        log "  Restarting $svc..."
        if ! $DRY_RUN; then
            docker compose up -d --force-recreate "$svc"
            sleep 5
        fi
    done
else
    log "[5/6] Skipping Celery worker restart"
fi

# ------------------------------------------------------------------
# 6. Post-rollback verification
# ------------------------------------------------------------------
log "[6/6] Post-rollback verification..."
if ! $DRY_RUN; then
    sleep 5
    echo "  livez:   $(curl -so /dev/null -w '%{http_code}' http://localhost:8000/livez)"
    echo "  healthz: $(curl -so /dev/null -w '%{http_code}' http://localhost:8000/healthz)"
    echo "  readyz:  $(curl -so /dev/null -w '%{http_code}' http://localhost:8000/readyz)"

    WORKERS=$(docker compose exec -T celery-beat \
        celery -A celery_app inspect ping --timeout 10 2>&1) || true
    if echo "$WORKERS" | grep -q "pong"; then
        log "  Celery workers: OK"
    else
        warn "  Celery workers may not be healthy. Check 'docker compose logs celery-beat'"
    fi

    log "=== Rollback to $TARGET_VERSION complete ==="
fi
