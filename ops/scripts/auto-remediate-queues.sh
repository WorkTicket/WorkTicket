#!/usr/bin/env bash
# Auto-remediation script for Celery queue depth.
# Designed to be called by a cron job or Kubernetes HPA sidecar.
# Scales celery-worker-default replicas when queue depth exceeds thresholds.
#
# Usage: ./auto-remediate-queues.sh [--dry-run]
# Environment:
#   PROMETHEUS_URL - Prometheus endpoint (default: http://localhost:9090)
#   CELERY_SERVICE - Docker Compose service name (default: celery-worker-default)
#   MIN_REPLICAS   - Minimum worker count (default: 1)
#   MAX_REPLICAS   - Maximum worker count (default: 10)
#   SCALE_UP_THRESHOLD   - Queue depth to trigger scale-up (default: 50)
#   SCALE_DOWN_THRESHOLD - Queue depth to trigger scale-down (default: 10)

set -euo pipefail

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
CELERY_SERVICE="${CELERY_SERVICE:-celery-worker-default}"
MIN_REPLICAS="${MIN_REPLICAS:-1}"
MAX_REPLICAS="${MAX_REPLICAS:-10}"
SCALE_UP_THRESHOLD="${SCALE_UP_THRESHOLD:-50}"
SCALE_DOWN_THRESHOLD="${SCALE_DOWN_THRESHOLD:-10}"
DRY_RUN="${1:-}"

# Get current queue depth from Prometheus
QUEUE_DEPTH=$(curl -sf "${PROMETHEUS_URL}/api/v1/query" \
  --data-urlencode "query=workticket_celery_queue_depth_default" \
  | python3 -c "import sys,json; print(int(json.load(sys.stdin)['data']['result'][0]['value'][1]))" 2>/dev/null || echo "0")

echo "Queue depth: ${QUEUE_DEPTH}"

# Get current replica count
if command -v docker &>/dev/null; then
  CURRENT_REPLICAS=$(docker compose ps "${CELERY_SERVICE}" 2>/dev/null | grep -c "Up" || echo "1")
elif command -v kubectl &>/dev/null; then
  CURRENT_REPLICAS=$(kubectl get deployment "${CELERY_SERVICE}" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
else
  CURRENT_REPLICAS=1
fi

echo "Current replicas: ${CURRENT_REPLICAS}"

if [ "${QUEUE_DEPTH}" -gt "${SCALE_UP_THRESHOLD}" ] && [ "${CURRENT_REPLICAS}" -lt "${MAX_REPLICAS}" ]; then
  TARGET=$((CURRENT_REPLICAS + 1))
  echo "Scaling UP ${CELERY_SERVICE} to ${TARGET} (queue=${QUEUE_DEPTH}, threshold=${SCALE_UP_THRESHOLD})"
  if [ "${DRY_RUN}" != "--dry-run" ]; then
    if command -v docker &>/dev/null; then
      docker compose up -d --scale "${CELERY_SERVICE}=${TARGET}" --no-recreate "${CELERY_SERVICE}"
    elif command -v kubectl &>/dev/null; then
      kubectl scale deployment "${CELERY_SERVICE}" --replicas="${TARGET}"
    fi
  fi
elif [ "${QUEUE_DEPTH}" -lt "${SCALE_DOWN_THRESHOLD}" ] && [ "${CURRENT_REPLICAS}" -gt "${MIN_REPLICAS}" ]; then
  TARGET=$((CURRENT_REPLICAS - 1))
  echo "Scaling DOWN ${CELERY_SERVICE} to ${TARGET} (queue=${QUEUE_DEPTH}, threshold=${SCALE_DOWN_THRESHOLD})"
  if [ "${DRY_RUN}" != "--dry-run" ]; then
    if command -v docker &>/dev/null; then
      docker compose up -d --scale "${CELERY_SERVICE}=${TARGET}" --no-recreate "${CELERY_SERVICE}"
    elif command -v kubectl &>/dev/null; then
      kubectl scale deployment "${CELERY_SERVICE}" --replicas="${TARGET}"
    fi
  fi
else
  echo "No scaling action needed (queue ${QUEUE_DEPTH}, replicas ${CURRENT_REPLICAS})"
fi
