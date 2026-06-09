# Tenant Abuse Incident Runbook

## Detection

### Automated Detection
- **Risk score > 50:** Automatic quota halved (`BillingAccount.risk_score`)
- **Risk score > 70:** AI processing automatically disabled (`ai_disabled=True`)
- **Spend alerts:** Daily spending monitor fires when usage exceeds configured thresholds
- **Spike detection:** `AbuseDetector` detects anomalous request patterns (rate, volume, content)
- **Rate limit exhaustion:** Single tenant exceeding per-IP or per-tenant rate limits
- **Concurrent job spike:** Company concurrency limit persistently maxed out

### Prometheus Alerts
- `BillingDebtThreshold` — acu_debt exceeded monthly quota
- `RateLimiterRedisDown` — combined with unusual traffic patterns
- `CeleryQueueDepth` alerts for a single tenant's queue growing unusually
- Custom: anomaly detection on per-tenant request patterns

## Investigation Steps

### 1. Identify the Tenant
```sql
-- Check billing account for risk indicators
SELECT company_id, risk_score, ai_disabled, ai_disabled_reason,
       monthly_quota_acu, used_acu, reserved_acu, acu_debt
FROM billing_accounts
WHERE risk_score > 30 OR ai_disabled = true
ORDER BY risk_score DESC;
```

### 2. Review Usage Patterns
```sql
-- Check recent usage_ledger for the tenant
SELECT created_at, job_id, amount_acu, cost_usd
FROM usage_ledger
WHERE company_id = '<company_id>'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 100;
```

### 3. Check Abuse Detector State
```python
# Via API or Django shell
from app.billing.abuse import abuse_detector
stats = abuse_detector.get_stats('<company_id>')
# Returns: request_count, spike_count, last_request, risk_score
```

### 4. Review Audit Logs
```sql
SELECT created_at, user_id, action, details
FROM job_audit_logs
WHERE company_id = '<company_id>'
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

### 5. Check Rate Limit Exhaustion
```bash
# Redis rate limit keys for the tenant
redis-cli keys "rl:*:<company_id>:*"
redis-cli keys "spike:<company_id>:*"
redis-cli keys "spend:<company_id>:*"
```

## Actions

### Automatic (risk score based)
| Risk Score | Action |
|------------|--------|
| > 30 | Logged for monitoring |
| > 50 | Monthly quota halved automatically |
| > 70 | AI processing disabled, notification sent |
| > 90 | Rate limits tightened, can only be re-enabled by admin |

### Manual Intervention
1. **Disable AI for a tenant:**
   ```bash
   curl -X POST <api>/api/v1/billing/disable-ai \
     -H "Authorization: Bearer <admin-token>" \
     -d '{"company_id": "<company_id>"}'
   ```

2. **Re-enable AI after investigation:**
   ```bash
   curl -X POST <api>/api/v1/billing/enable-ai \
     -H "Authorization: Bearer <admin-token>" \
     -d '{"company_id": "<company_id>"}'
   ```

3. **Reset risk score (if false positive):**
   ```python
   # Via admin API
   from app.billing.abuse import abuse_detector
   await abuse_detector.reset_risk_score('<company_id>')
   ```

4. **Full tenant suspension (extreme cases):**
   - Revoke all active sessions via Clerk dashboard
   - Set `user.is_active = False` for all tenant users
   - Set `company.is_suspended = True`
   - Mark billing account `ai_disabled = True`

## Recovery

### After Abuse Investigation Clears
1. Risk scores decay automatically (5 points per cycle per `decay_risk_scores_task`)
2. AI can be re-enabled via API after manual review
3. Quota returns to normal when risk_score drops below threshold
4. Normal rate limits restored

### Manual Recovery Steps
```bash
# Clear abuse flags
curl -X POST <api>/api/v1/billing/enable-ai \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"company_id": "<company_id>"}'

# Reset risk score
curl -X POST <api>/api/v1/admin/reset-risk-score \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"company_id": "<company_id>"}'
```

## Fraud Patterns to Watch
| Pattern | Indicators | Action |
|---------|-----------|--------|
| Automated scraping | High request count, regular intervals, no media uploads | Rate limit, investigate IP |
| Free tier abuse | Multiple accounts from same IP, minimal engagement | Merge or suspend duplicates |
| Prompt injection attempts | High rejection rate from AI sanitizer, malformed inputs | Block IP, audit content |
| Payment fraud | Multiple failed payment attempts, rapid plan changes | Lock account, manual review |
| Credential stuffing | Many failed auth attempts from different IPs | Check Clerk logs, enable MFA |

## Escalation
| Severity | Action | Contact |
|----------|--------|---------|
| Risk score > 70 | Automated AI disable + alert | On-call engineer |
| Potential fraud | Manual investigation | Security team |
| Confirmed abuse | Tenant suspension | CTO + legal |
| Data exfiltration risk | Immediate full suspension | CTO + security team |

## Related Runbooks
- `billing-corruption.md` — if abuse caused billing discrepancies
- `acu-debt-reconciliation.md` — if debt needs manual reconciliation
- `hmac-key-rotation.md` — if task signing key suspected compromised
