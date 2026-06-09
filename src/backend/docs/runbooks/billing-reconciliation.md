# Billing Reconciliation Failure Runbook

## Symptoms
- `workticket_acu_debt_total > 0`
- `BillingDriftHigh` alert (>5% cost drift)
- `BillingDebtThreshold` alert (acu_debt > $1 threshold)
- Underflow events in logs: "billing reconciliation underflow"

## Steps

### 1. Query acu_debt across accounts
```sql
SELECT company_id, reserved_acu, used_acu, acu_debt, monthly_quota_acu, reset_at
FROM billing_accounts
WHERE acu_debt > 0.01
ORDER BY acu_debt DESC;
```

### 2. Query recent reconciliation errors
```sql
SELECT ul.company_id, ul.job_id, ul.estimated_cost_usd, ul.cost_usd, ul.created_at
FROM usage_ledger ul
WHERE ul.created_at > now() - interval '1 hour'
  AND ABS(ul.cost_usd - ul.estimated_cost_usd) > 0.001
ORDER BY ul.created_at DESC;
```

### 3. Issue manual credits (if needed)
```sql
-- Insert a manual credit ledger entry
INSERT INTO usage_ledger (id, company_id, job_id, cost_usd, is_credit, credit_reason, created_at)
VALUES (gen_random_uuid(), '<company_id>', NULL, -<amount>, true, 'Manual credit - reconciliation fix', now());
```

### 4. Force debt collection
If the hourly `collect_billing_debt` task hasn't run:
```bash
celery -A celery_app call collect_billing_debt
```

### 5. Verify billing integrity
```sql
-- Check for negative reserved_acu (should never happen)
SELECT company_id, reserved_acu
FROM billing_accounts
WHERE reserved_acu < 0;
```

### 6. Check reconciliation logs
Search for "BillingIntegrityError" or "reconciliation underflow" in application logs.

## Prevention
- Ensure `reserved_acu >= reserved` before subtraction in `reconcile_cost`
- The hourly `collect_billing_debt` beat task automatically collects debt
- Monitor `workticket_billing_drift_pct` for early warning
