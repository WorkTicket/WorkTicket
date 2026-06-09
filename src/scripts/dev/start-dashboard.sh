#!/bin/bash
set -e

cd "$(dirname "$0")/../../web-dashboard"

echo "=== Starting Web Dashboard ==="

npm run dev
