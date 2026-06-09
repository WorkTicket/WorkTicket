# Billing Corruption Detection Runbook

## Billing Period Drift Detection (C-3)
Stripe webhook events from prior billing periods can corrupt current period state.
### Detection
- Check for `StripeEventFromPriorPeriod` log warnings:
  ```
  grep "PRIOR billing period" celery_app.log
  ```
- SQL: Find accounts where billing_period_start is inconsistent with event timestamps
  ```sql
  SELECT ba.company_id, ba.billing_period_start, ba.plan
  FROM billing_accounts ba
  WHERE ba.billing_period_start IS NOT NULL
    AND ba.billing_period_start < NOW() - INTERVAL '35 days';
  ```
### Prevention
- All webhook handlers validate `event.created` against `account.billing_period_start`
- Events from prior periods are rejected with HTTP 400
- Monitor `workticket_stripe_webhook_lock_contention_total` metric

## Detection

### SQL Queries to Detect Double-Charging

```sql
-- Find accounts where used_acu + reserved_acu > monthly_quota_acu
SELECT company_id, plan, monthly_quota_acu, used_acu, reserved_acu, acu_debt
FROM billing_accounts
WHERE (used_acu + reserved_acu) > monthly_quota_acu * 1.05;
```

```sql
-- Find concurrent quota resets (same company, same period)
SELECT company_id, COUNT(*) as reset_count, MIN(reset_at) as first, MAX(reset_at) as last
FROM billing_accounts
GROUP BY company_id
HAVING COUNT(*) > 1;
```

```sql
-- Per-company ACU drift analysis
SELECT
  ba.company_id,
  ba.used_acu,
  SUM(ul.cost_acu) as ledger_total,
  ba.used_acu - COALESCE(SUM(ul.cost_acu), 0) as drift
FROM billing_accounts ba
LEFT JOIN usage_ledger ul ON ul.company_id = ba.company_id
  AND ul.created_at > ba.billing_period_start
GROUP BY ba.company_id, ba.used_acu
HAVING ABS(ba.used_acu - COALESCE(SUM(ul.cost_acu), 0)) > 0.01;
```

## Recovery

### Manual Credit Issuance

```python
from app.billing.credits import grant_credit
from app.database import AsyncSessionLocal

async def issue_refund(company_id, amount_acu, reason):
    async with AsyncSessionLocal() as db:
        result = await grant_credit(
            db=db, company_id=company_id,
            job_id=None, amount_acu=amount_acu,
            reason=f"manual_correction: {reason}",
            granted_by="admin",
        )
        await db.commit()
        return result
```

### Force Account Reset

```sql
UPDATE billing_accounts
SET used_acu = 0, reserved_acu = 0, acu_debt = 0,
    reset_at = NOW() + INTERVAL '30 days',
    billing_period_start = NOW()
WHERE company_id = '<company-uuid>';
```

## Monitoring

- Alert on `workticket_billing_reconciliation_integrity_error_total > 0`
- Alert on `workticket_acu_debt_total > 100`
- Grafana: `workticket_db_pool_circuit_breaker` should be 0
