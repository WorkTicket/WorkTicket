# Runbook: ACU Debt Reconciliation

## Symptoms
- `ACUDebtAccumulated` alert firing
- `workticket_acu_debt_total` > 0
- Billing inconsistency suspected

## Root Causes
1. **Task retry during reconciliation** — `reconcile_cost` runs again on retry but ledger entry already exists
2. **Quota reset race** — `reset_billing_quotas` resets reserved_acu to 0 while a task is in flight
3. **cleanup_stale_jobs race** — stale job cleanup releases quota while task is still processing
4. **Redis eviction** — Jobs are lost but reservations are never released

## Investigation

### 1. Find companies with debt
```sql
SELECT company_id, acu_debt, reserved_acu, used_acu, monthly_quota_acu
FROM billing_accounts
WHERE acu_debt > 0;
```

### 2. Find jobs that may have contributed to debt
```sql
SELECT ul.*, j.ai_processing_state
FROM usage_ledger ul
JOIN jobs j ON j.id = ul.job_id
WHERE ul.company_id = '<company_id>'
  AND ul.created_at > NOW() - INTERVAL '7 days';
```

### 3. Cross-reference with retries
```sql
-- Find jobs that were retried during reconciliation window
SELECT dlq.*
FROM dead_letter_jobs dlq
WHERE dlq.company_id = '<company_id>'
  AND dlq.created_at > NOW() - INTERVAL '7 days';
```

## Manual Fix

### Zero out the debt for a company
```sql
BEGIN;
UPDATE billing_accounts
SET acu_debt = 0.0
WHERE company_id = '<company_id>'
  AND acu_debt > 0;
COMMIT;
```

### Full reconciliation for a company
```sql
BEGIN;
-- Calculate actual used ACU from ledger
WITH actual_usage AS (
  SELECT company_id, SUM(cost_usd) / 0.001 AS actual_acu
  FROM usage_ledger
  WHERE company_id = '<company_id>'
    AND created_at >= (SELECT billing_period_start FROM billing_accounts WHERE company_id = '<company_id>')
  GROUP BY company_id
)
UPDATE billing_accounts
SET
  used_acu = COALESCE((SELECT actual_acu FROM actual_usage WHERE company_id = billing_accounts.company_id), 0),
  reserved_acu = 0,
  acu_debt = 0
WHERE company_id = '<company_id>';
COMMIT;
```

## Prevention
- Fix is already in place: `reconcile_cost` now checks for existing ledger entry BEFORE modifying balances
- Monitor `billing_reconciliation_underflow_total` counter
- `reset_billing_quotas` uses NOWAIT + individual retry instead of skip_locked
