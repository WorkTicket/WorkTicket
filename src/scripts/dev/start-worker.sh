#!/bin/bash
set -e

cd "$(dirname "$0")/../../backend"

echo "=== Starting Celery Worker ==="
echo "  Redis: $REDIS_URL"
echo ""

celery -A celery_app worker --loglevel=info --concurrency=2
