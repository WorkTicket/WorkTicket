#!/bin/bash
# Pin Docker images to SHA256 digests for reproducible builds.
# Usage: bash ops/pin-docker-images.sh [compose-file]
# Default: src/docker-compose.yml
#
# This script reads each `image:` line from the compose file, pulls the image,
# resolves its digest, and rewrites the line to include the digest.
#
# Example:
#   image: redis:7-alpine
#   becomes:
#   image: redis:7-alpine@sha256:abc123...

set -euo pipefail

COMPOSE_FILE="${1:-src/docker-compose.yml}"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: Compose file not found: $COMPOSE_FILE"
    exit 1
fi

TMP_FILE=$(mktemp)
cp "$COMPOSE_FILE" "$TMP_FILE"

pinned_count=0
skip_count=0

while IFS= read -r line; do
    if [[ $line =~ ^[[:space:]]*image:[[:space:]]*([^@]+)$ ]]; then
        IMAGE="${BASH_REMATCH[1]}"
        # Skip build-context images (those without a registry/tag pattern)
        if [[ $IMAGE != *:* ]]; then
            ((skip_count++))
            continue
        fi
        echo "Resolving digest for $IMAGE ..."
        DIGEST=$(docker pull "$IMAGE" 2>/dev/null | grep -oP 'Digest: \K(sha256:[a-f0-9]+)' || true)
        if [ -n "$DIGEST" ]; then
            PINNED="${IMAGE}@${DIGEST}"
            sed -i "s|image: $IMAGE|image: $PINNED|g" "$COMPOSE_FILE"
            echo "  Pinned: $PINNED"
            ((pinned_count++))
        else
            echo "  WARNING: Could not resolve digest for $IMAGE"
            ((skip_count++))
        fi
    fi
done < "$TMP_FILE"

rm "$TMP_FILE"
echo ""
echo "Done. Pinned: $pinned_count, Skipped: $skip_count"
echo "Review changes with: git diff $COMPOSE_FILE"
