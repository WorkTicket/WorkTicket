# Incident Response

## Severity Definitions

| Severity | Definition | Response Time | Examples |
|----------|-----------|---------------|---------|
| **SEV1** | Complete service outage or data loss | 15 min | Redis OOM, Stripe billing divergence, DB corruption |
| **SEV2** | Major feature degradation | 30 min | WebSocket down, Celery queue stuck, billing not resetting |
| **SEV3** | Minor feature degradation | 2 hours | WS re-auth slow, occasional 503s, DLQ growing |
| **SEV4** | Cosmetic / non-urgent | Next business day | Dashboard metric missing, stale runbook |

## Escalation Matrix

| Role | Contact | SEV1 Backup |
|------|---------|-------------|
| On-call Engineer | PagerDuty alert | Slack #workticket-ops |
| SRE Lead | +1-555-0100 | Secondary SRE |
| Engineering Manager | +1-555-0101 | CTO |
| CTO | +1-555-0102 | CEO |

## Communication Channels

- **Public status**: `status.workticket.com`
- **Internal Slack**: #workticket-ops (SEV1/SEV2), #workticket-dev (SEV3/SEV4)
- **On-call handoff**: Daily at 09:00 UTC

## Incident Lifecycle

1. **Detection**: Alert fires or customer reports issue
2. **Acknowledge**: Responder claims incident in Slack within SLO
3. **Triage**: Determine severity, gather evidence, check runbooks
4. **Mitigate**: Apply mitigation (rollback, scale, kill queries)
5. **Resolve**: Verify fix, confirm recovery
6. **Postmortem**: Within 48 hours, write root cause analysis

## Postmortem Template

```markdown
## Incident: [TITLE]
- **Date**: YYYY-MM-DD
- **Duration**: Xh Ym
- **Severity**: SEV1/SEV2/SEV3
- **Impact**: X users affected, $Y revenue impact

## Timeline
- HH:MM - Detection
- HH:MM - Acknowledged
- HH:MM - Mitigation started
- HH:MM - Resolved

## Root Cause
[Description of what went wrong]

## Contributing Factors
- Factor 1
- Factor 2

## Action Items
- [ ] Fix 1 (owner, due date)
- [ ] Fix 2 (owner, due date)

## Lessons Learned
- What went well
- What went wrong
- What to improve
```

## PagerDuty Rotation

- Primary: Week-long shifts, Mon 09:00 UTC
- Secondary: Follows primary
- Schedule: Defined in PagerDuty
- Handoff: Document active incidents, pending issues, ongoing investigations
