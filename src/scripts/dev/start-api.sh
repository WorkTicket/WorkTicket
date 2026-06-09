#!/bin/bash
set -e

cd "$(dirname "$0")/../../backend"

echo "=== Starting Backend API ==="
echo "  Database: $DATABASE_URL"
echo "  Redis:    $REDIS_URL"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
