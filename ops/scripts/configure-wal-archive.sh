#!/usr/bin/env bash
# Configure PostgreSQL WAL archiving for PITR (point-in-time recovery).
# This script writes the archive_command into postgresql.conf and creates
# the archive directory. Run on the PostgreSQL primary node.
#
# Usage: sudo ./configure-wal-archive.sh [archive_dir] [retain_days]
#   archive_dir  - Destination for WAL segments (default: /var/lib/postgresql/wal_archive)
#   retain_days  - How many days to retain archived WALs (default: 7)

set -euo pipefail

ARCHIVE_DIR="${1:-/var/lib/postgresql/wal_archive}"
RETAIN_DAYS="${2:-7}"
PG_CONF="${PGDATA:-/var/lib/postgresql/data}/postgresql.conf"

echo "=== WAL Archiving Configuration ==="
echo "Archive dir:     ${ARCHIVE_DIR}"
echo "Retain days:     ${RETAIN_DAYS}"
echo "PostgreSQL conf: ${PG_CONF}"
echo ""

# Create archive directory with correct ownership
if [ ! -d "${ARCHIVE_DIR}" ]; then
    echo "Creating archive directory: ${ARCHIVE_DIR}"
    mkdir -p "${ARCHIVE_DIR}"
    chown postgres:postgres "${ARCHIVE_DIR}"
    chmod 700 "${ARCHIVE_DIR}"
fi

# Enable archiving in postgresql.conf
echo "Configuring WAL archiving in ${PG_CONF}..."

sed -i \
  -e "s/^#*wal_level = .*/wal_level = replica/" \
  -e "s|^#*archive_mode = .*|archive_mode = on|" \
  -e "s|^#*archive_command = .*|archive_command = 'test ! -f ${ARCHIVE_DIR}/%f \&\& cp %p ${ARCHIVE_DIR}/%f'|" \
  -e "s/^#*archive_timeout = .*/archive_timeout = 300/" \
  -e "s/^#*max_wal_senders = .*/max_wal_senders = 5/" \
  "${PG_CONF}"

echo ""

# Install archive cleanup cron job
CRON_JOB="find ${ARCHIVE_DIR} -type f -name '*.gz' -mtime +${RETAIN_DAYS} -delete"
if ! (crontab -l 2>/dev/null | grep -q "${ARCHIVE_DIR}"); then
    (crontab -l 2>/dev/null; echo "0 3 * * * ${CRON_JOB}") | crontab -
    echo "Installed cron job to purge WALs older than ${RETAIN_DAYS} days"
fi

echo ""
echo "=== Configuration Complete ==="
echo "Restart PostgreSQL to apply changes: sudo systemctl restart postgresql"
echo ""
echo "Verify with:"
echo "  sudo -u postgres psql -c 'SHOW wal_level;'"
echo "  sudo -u postgres psql -c 'SHOW archive_mode;'"
echo "  sudo -u postgres psql -c 'SHOW archive_command;'"
