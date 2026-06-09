#!/bin/bash
set -e

cd "$(dirname "$0")/../../mobile-app"

echo "=== Starting Mobile App (Expo) ==="
echo "  Use Expo Go to scan the QR code"
echo "  Or press '?' for tunnel options"
echo ""

npx expo start --tunnel
