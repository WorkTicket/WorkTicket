#!/usr/bin/env bash
set -euo pipefail

# Rollback Script
# Reverts to the previous deployment tag.

PREVIOUS_TAG="${1:-workticket-backend:previous}"
CURRENT_TAG="${2:-workticket-backend:latest}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Starting rollback: ${CURRENT_TAG} -> ${PREVIOUS_TAG}"

if ! docker image inspect "${PREVIOUS_TAG}" &>/dev/null; then
    log "ERROR: Previous image ${PREVIOUS_TAG} not found"
    exit 1
fi

# Retag previous as latest
docker tag "${PREVIOUS_TAG}" "${CURRENT_TAG}"
log "Tagged ${PREVIOUS_TAG} as ${CURRENT_TAG}"

# Follow deploy sequencing
log "Stopping celery-beat..."
docker compose stop celery-beat || log "Warning: beat stop failed"

log "Stopping celery workers..."
docker compose stop celery-worker-default celery-worker-text celery-worker-image celery-worker-audio celery-worker-beat || log "Warning: worker stop failed"

log "Starting backend..."
docker compose up -d backend || { log "ERROR: backend start failed"; exit 1; }

log "Checking for schema rollback..."
if [ -n "${ALEMBIC_DOWN_REVISION:-}" ]; then
    docker compose exec -T backend alembic downgrade "${ALEMBIC_DOWN_REVISION}" || log "Warning: downgrade failed"
fi

log "Starting celery workers..."
docker compose up -d celery-worker-default celery-worker-text celery-worker-image celery-worker-audio celery-worker-beat || { log "ERROR: worker start failed"; exit 1; }

log "Starting celery-beat..."
docker compose up -d celery-beat || { log "ERROR: beat start failed"; exit 1; }

log "Rollback completed successfully"
