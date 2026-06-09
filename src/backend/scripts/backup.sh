#!/usr/bin/env bash
set -euo pipefail

# Database Backup Script
# Designed to be run as a host-level cron job (not from Celery)
# Backs up the PostgreSQL database, compresses it, and manages retention.

BACKUP_DIR="${BACKUP_DIR:-/tmp/workticket-backup}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="workticket_db_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${FILENAME}"
EXIT_CODE=0

# Database connection parameters (passed via environment or defaults)
PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-workticket}"

mkdir -p "${BACKUP_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Starting database backup to ${BACKUP_PATH}"

if ! pg_dump \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="${BACKUP_PATH}" 2>&1; then
    log "ERROR: pg_dump failed"
    EXIT_CODE=1
fi

if [ ${EXIT_CODE} -eq 0 ]; then
    BACKUP_SIZE=$(stat -c%s "${BACKUP_PATH}" 2>/dev/null || stat -f%z "${BACKUP_PATH}" 2>/dev/null || echo "unknown")
    log "Backup completed: ${FILENAME} (${BACKUP_SIZE} bytes)"

    # Validate backup integrity with pg_restore -l (CRITICAL-2)
    log "Validating backup integrity..."
    if pg_restore -l "${BACKUP_PATH}" > /dev/null 2>&1; then
        log "Backup integrity validation PASSED"
    else
        log "ERROR: Backup integrity validation FAILED — pg_restore -l reports corruption"
        mv "${BACKUP_PATH}" "${BACKUP_PATH}.corrupted"
        EXIT_CODE=1
    fi

    # Generate SHA-256 checksum
    CHECKSUM_FILE="${BACKUP_PATH}.sha256"
    sha256sum "${BACKUP_PATH}" > "${CHECKSUM_FILE}"
    log "Backup checksum: $(cat ${CHECKSUM_FILE})"
fi

# Retention: remove backups older than RETENTION_DAYS
if [ ${EXIT_CODE} -eq 0 ]; then
    log "Cleaning up backups older than ${RETENTION_DAYS} days"
    find "${BACKUP_DIR}" -name "workticket_db_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
fi

# Upload to S3 if bucket is configured
if [ -n "${S3_BUCKET}" ] && [ ${EXIT_CODE} -eq 0 ]; then
    if command -v aws &>/dev/null; then
        log "Uploading to S3 bucket: ${S3_BUCKET}"
        aws s3 cp "${BACKUP_PATH}" "s3://${S3_BUCKET}/database/${FILENAME}" --only-show-errors || log "WARNING: S3 upload failed"
    else
        log "WARNING: aws CLI not found, skipping S3 upload"
    fi
fi

if [ ${EXIT_CODE} -eq 0 ]; then
    log "Backup completed successfully"
else
    log "Backup FAILED"
fi

exit ${EXIT_CODE}
