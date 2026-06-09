#!/bin/bash
set -euo pipefail

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup-file.tar.gz>"
  echo "       $0 latest  (restores from most recent S3 backup)"
  exit 1
fi

S3_BUCKET="${S3_BUCKET:-s3://workticket-backups}"
RESTORE_DIR=$(mktemp -d)

if [ "$BACKUP_FILE" = "latest" ]; then
  echo "Fetching latest backup from $S3_BUCKET..."
  LATEST=$(aws s3 ls "$S3_BUCKET/" | sort | tail -n 1 | awk '{print $4}')
  if [ -z "$LATEST" ]; then
    echo "No backups found in $S3_BUCKET"
    exit 1
  fi
  aws s3 cp "$S3_BUCKET/$LATEST" "$RESTORE_DIR/$LATEST"
  BACKUP_FILE="$RESTORE_DIR/$LATEST"
fi

echo "=== WorkTicket Restore ==="
echo "Restoring from: $BACKUP_FILE"

tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"

echo "Restoring PostgreSQL..."
PGPASSWORD="${PGPASSWORD:?PGPASSWORD must be set}" pg_restore \
  -h "${PGHOST:-localhost}" \
  -U "${PGUSER:-postgres}" \
  -d "${PGDATABASE:-workticket}" \
  --clean --if-exists \
  "$RESTORE_DIR/postgres_"*.dump
echo "  -> postgres restored"

echo "Restoring Redis..."
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHALL
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --pipe < "$RESTORE_DIR/redis_"*.rdb
echo "  -> redis restored"

rm -rf "$RESTORE_DIR"
echo "Restore complete!"
