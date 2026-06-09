#!/usr/bin/env bash
# rollback-023.sh — Rollback migration 023 (UsageLedger partitioning)
# D3: Run this ONLY if migration 023 has caused production issues.
# Requires: psql, PGPASSWORD env var, rollback window with no writes.
set -euo pipefail

DB_URL="${DATABASE_URL:?DATABASE_URL must be set to the production database URL}"
echo "=== Migration 023 Rollback ==="
echo "DB: $DB_URL"
echo "WARNING: This will briefly lock usage_ledger. Ensure no writes during rollback."
read -rp "Continue? [y/N] " confirm
[[ "$confirm" == "y" || "$confirm" == "Y" ]] || exit 1

psql "$DB_URL" <<'SQL'
BEGIN;
-- 1. Check current migration version
SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;

-- 2. Create backup of all UsageLedger data
CREATE TABLE IF NOT EXISTS usage_ledger_backup_023 AS SELECT * FROM usage_ledger;

-- 3. Drop dependent foreign keys (if any reference usage_ledger)
-- (Add DROP statements here if child tables reference the partitioned table)

-- 4. Drop partitioned table and its partitions
DROP TABLE IF EXISTS usage_ledger CASCADE;

-- 5. Recreate as unpartitioned table with original schema
CREATE TABLE usage_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES billing_accounts(id),
    job_id UUID,
    text_units INTEGER DEFAULT 1,
    vision_units INTEGER DEFAULT 0,
    audio_units INTEGER DEFAULT 0,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    model_used VARCHAR(64),
    execution_time_ms INTEGER DEFAULT 0,
    billing_period VARCHAR(7),
    user_id VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Re-insert data from backup
INSERT INTO usage_ledger SELECT * FROM usage_ledger_backup_023;

-- 7. Recreate indexes
CREATE INDEX idx_usage_ledger_company_id ON usage_ledger(company_id);
CREATE INDEX idx_usage_ledger_job_id ON usage_ledger(job_id);
CREATE INDEX idx_usage_ledger_period ON usage_ledger(billing_period);
CREATE INDEX idx_usage_ledger_created_at ON usage_ledger(created_at);

-- 8. Update alembic_version to migration 022
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('022_previous_migration');

-- 9. Cleanup backup (verify data first!)
-- DROP TABLE IF EXISTS usage_ledger_backup_023;
COMMIT;

SELECT COUNT(*) AS total_rows_restored FROM usage_ledger;
echo "Rollback complete. Verify data integrity before dropping backup table."
SQL
