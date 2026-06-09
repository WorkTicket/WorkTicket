# Migration Rollback Runbook

## General Rollback Steps

1. **Identify current migration**
   ```bash
   cd backend
   alembic current
   ```

2. **Rollback one step**
   ```bash
   alembic downgrade -1
   ```

3. **Verify rollback**
   ```bash
   alembic current
   psql -c "\dt" | grep usage_ledger  # check table exists
   ```

## Migration 023 (UsageLedger Partitioning) Rollback

This migration uses `CREATE TABLE ... PARTITION BY RANGE`. Rollback requires data reconstruction.

**Script**: `backend/scripts/rollback-023.sh`

**Manual steps**:
```sql
BEGIN;
CREATE TABLE usage_ledger_backup AS SELECT * FROM usage_ledger;
DROP TABLE usage_ledger CASCADE;
CREATE TABLE usage_ledger (LIKE usage_ledger_backup INCLUDING ALL);
ALTER TABLE usage_ledger ADD PRIMARY KEY (id);
INSERT INTO usage_ledger SELECT * FROM usage_ledger_backup;
DROP TABLE usage_ledger_backup;
COMMIT;
```

**Verify**: `SELECT count(*) FROM usage_ledger;` matches expected row count.

**Note**: Must be validated in staging at least once before production use.

## Critical Migrations
| Migration | Risk | Rollback Complexity |
|-----------|------|---------------------|
| 021_add_dead_letter_jobs | Low | `downgrade -1` drops table |
| 023_partition_usage_ledger | High | Requires data reconstruction |
| 024_add_state_cycle_counter | Low | `downgrade -1` drops column |
