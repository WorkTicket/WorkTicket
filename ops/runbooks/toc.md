# Runbooks Index

| Runbook | Location | Description |
|---------|----------|-------------|
| Rolling Restart | `ops/runbooks/rolling-restart.md` | Zero-downtime deployment procedure |
| Rollback (PS) | `ops/scripts/rollback.ps1` | PowerShell rollback script |
| Rollback (sh) | `ops/scripts/rollback.sh` | Bash rollback script |
| Redis OOM | `ops/runbooks/redis-oom.md` | Broker Redis memory exhaustion response |
| DLQ Recovery | `ops/runbooks/dlq-recovery.md` | Dead letter queue drain and replay |
| Worker Stuck | `ops/runbooks/worker-stuck.md` | Stuck/deadlocked worker recovery |
| Concurrency Drift | `ops/runbooks/concurrency-drift.md` | Stale concurrency lock keys |
| DB Saturation | `ops/runbooks/db-saturation.md` | Connection pool exhaustion response |
| Queue Backup | `ops/runbooks/queue-backup.md` | Celery queue backlog drain |
| Failed Deploy | `ops/runbooks/failed-deploy.md` | Rollback procedure |
| Incident Response | `ops/runbooks/INCIDENT_RESPONSE.md` | Severity definitions, escalation |
| Chaos Testing | `ops/runbooks/chaos-testing.md` | Running chaos engineering tests |
| Operator Onboarding | `docs/runbooks/operator-onboarding.md` | Training guide for new runbooks and signals |

## Quick Reference

**Rollback to previous version:**
```bash
# PowerShell
.\ops\scripts\rollback.ps1 -TargetVersion v1.0.0-beta.9 -RollbackMigration

# Bash
./ops/scripts/rollback.sh v1.0.0-beta.9 --rollback-migrate
```

**Dry run (preview only):**
```bash
.\ops\scripts\rollback.ps1 -TargetVersion v1.0.0-beta.9 -DryRun
```
