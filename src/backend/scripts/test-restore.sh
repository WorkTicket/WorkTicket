#!/usr/bin/env bash
set -euo pipefail

# Automated Restore Test (CRITICAL-2)
# Restores the latest backup to a temporary database to verify integrity.

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TEST_DB="workticket_restore_test_$(date +%Y%m%d_%H%M%S)"
PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-}"
LOGFILE="/tmp/restore_test_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOGFILE}"
}

cleanup() {
    log "Cleaning up test database ${TEST_DB}..."
    PGAPPNAME="restore_test" PGPASSWORD="${PGPASSWORD}" dropdb --if-exists \
        --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" "${TEST_DB}" 2>/dev/null || true
}

trap cleanup EXIT

# Find latest backup
LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/*.dump 2>/dev/null | head -1)
if [ -z "${LATEST_BACKUP}" ]; then
    log "ERROR: No backup files found in ${BACKUP_DIR}"
    exit 1
fi

log "Starting restore test with backup: ${LATEST_BACKUP}"

# Verify checksum if available
CHECKSUM_FILE="${LATEST_BACKUP}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    log "Verifying checksum..."
    if sha256sum -c "${CHECKSUM_FILE}" > /dev/null 2>&1; then
        log "Checksum verification PASSED"
    else
        log "ERROR: Checksum verification FAILED — backup may be corrupted"
        exit 1
    fi
else
    log "WARNING: No checksum file found — skipping checksum verification"
fi

# Create temporary database
log "Creating test database: ${TEST_DB}"
PGAPPNAME="restore_test" PGPASSWORD="${PGPASSWORD}" createdb \
    --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" "${TEST_DB}"

# Restore backup
log "Restoring backup to test database..."
if PGAPPNAME="restore_test" PGPASSWORD="${PGPASSWORD}" pg_restore \
    --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
    --dbname="${TEST_DB}" \
    --jobs=4 \
    --verbose \
    "${LATEST_BACKUP}" 2>&1 | tee -a "${LOGFILE}"; then
    log "Restore completed successfully"
else
    log "ERROR: Restore FAILED — backup is corrupted"
    exit 1
fi

# Verify data integrity by checking key tables
log "Verifying data integrity..."
TABLES=("companies" "users" "jobs" "billing_accounts" "usage_ledger" "invoices")
for table in "${TABLES[@]}"; do
    COUNT=$(PGAPPNAME="restore_test" PGPASSWORD="${PGPASSWORD}" psql \
        --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
        --dbname="${TEST_DB}" -t -c "SELECT count(*) FROM ${table}" 2>/dev/null | tr -d ' ')
    log "  Table ${table}: ${COUNT} rows"
done

log "Restore test PASSED — backup is valid and restorable"
exit 0
