#!/bin/bash
set -euo pipefail

# WorkTicket Automated Backup Script
# Usage: ./backup.sh [--s3-bucket s3://bucket/path] [--retain-days 30]

BACKUP_DIR="${BACKUP_DIR:-/tmp/workticket-backup}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/workticket_db_${TIMESTAMP}.dump"
REDIS_BACKUP="${BACKUP_DIR}/workticket_redis_${TIMESTAMP}.rdb"
LOG_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

mkdir -p "${BACKUP_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "Starting WorkTicket backup"

# Database backup
DB_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/workticket}"
# Convert async URL to sync URL for pg_dump
SYNC_URL="${DB_URL/+asyncpg/}"
log "Backing up database..."
if pg_dump "${SYNC_URL}" --format=custom --compress=9 --file="${BACKUP_FILE}"; then
    log "Database backup completed: $(ls -lh "${BACKUP_FILE}" | awk '{print $5}')"

    # Validate backup integrity with pg_restore -l (CRITICAL-2)
    log "Validating backup integrity..."
    if pg_restore -l "${BACKUP_FILE}" > /dev/null 2>&1; then
        log "Backup integrity validation PASSED"
    else
        log "ERROR: Backup integrity validation FAILED — pg_restore -l reports corruption"
        mv "${BACKUP_FILE}" "${BACKUP_FILE}.corrupted"
        exit 1
    fi

    # Generate SHA-256 checksum
    CHECKSUM_FILE="${BACKUP_FILE}.sha256"
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
    log "Backup checksum: $(cat ${CHECKSUM_FILE})"
else
    log "ERROR: Database backup failed"
    exit 1
fi

# Redis backup
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
REDIS_HOST=$(echo "${REDIS_URL}" | sed -n 's|redis://\(.*\):.*|\1|p')
REDIS_PORT=$(echo "${REDIS_URL}" | sed -n 's|redis://.*:\(.*\)/.*|\1|p')
: "${REDIS_HOST:=localhost}"
: "${REDIS_PORT:=6379}"

log "Backing up Redis..."
if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" --rdb "${REDIS_BACKUP}"; then
    log "Redis backup completed: $(ls -lh "${REDIS_BACKUP}" | awk '{print $5}')"
else
    log "WARNING: Redis backup failed (non-fatal)"
fi

# Upload to S3 if configured
if [ -n "${S3_BUCKET}" ]; then
    log "Uploading backup to ${S3_BUCKET}..."
    if aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/db/" 2>/dev/null; then
        log "Database backup uploaded successfully"
    else
        log "WARNING: S3 upload failed (non-fatal)"
    fi
fi

# Cleanup old backups
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "workticket_db_*.dump" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null
find "${BACKUP_DIR}" -name "workticket_redis_*.rdb" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null
find "${BACKUP_DIR}" -name "backup_*.log" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null

log "Backup completed successfully"
exit 0
