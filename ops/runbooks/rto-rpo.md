# RTO/RPO Runbook

## Recovery Objectives

| Metric | Target | Measurement | Validation |
|--------|--------|-------------|------------|
| **RTO** (Recovery Time Objective) | 1 hour | Time from incident declaration to full service restoration | Measured via Prometheus `up{job="api"}` gap duration |
| **RPO** (Recovery Point Objective) | 5 minutes | Maximum acceptable data loss measured in time | Achieved via PostgreSQL WAL archiving with 5-minute `archive_timeout` |

## RTO Measurement

RTO is measured from the moment an incident is declared (PagerDuty/Alertmanager webhook) to:
1. Service health checks return 200 on all endpoints
2. Celery workers are processing tasks
3. WebSocket connections are accepting new connections
4. Stripe webhooks are being processed

### RTO Exclusions
- Detection time (target: < 5 minutes via Prometheus Alertmanager)
- Communication time (target: < 5 minutes for on-call engineer to acknowledge)

## RPO Achievement

RPO of 5 minutes is achieved through:
- **PostgreSQL continuous WAL archiving** with `archive_timeout=300s` (5min)
- **Full database backups** performed daily at 02:00 UTC
- **WAL segments** archived to R2/S3 storage every 5 minutes or when 16MB threshold reached

### Backup Configuration
See `ops/scripts/configure-wal-archive.sh` for WAL archiving setup.

### Backup Verification Cadence
- **Automated restore test**: Runs daily at 03:00 UTC via `workticket_restore_test` Prometheus metric
- **Manual restore drill**: Monthly (first Monday of each month)
- **Integrity check**: `pg_restore -l` validation on every backup

## Alerting Integration

### Prometheus Alerts
| Alert | Rule | Severity |
|-------|------|----------|
| `BackupStalenessRPO` | `(time() - workticket_backup_last_success_timestamp) > 600` (RPO * 2 = 10min) | Critical |
| `RTOServiceDown` | `up{job="api"} == 0` for > 15 minutes | Critical |
| `BackupValidationFailed` | `workticket_backup_validation_success == 0` | Critical |
| `BackupStale` | Backup > 24h old | Critical |
| `RestoreTestFailed` | `workticket_restore_test_success == 0` | Critical |

### Escalation Path
1. **RPO breach warning** (backup > 5min stale): Slack #ops-alerts
2. **RPO breach critical** (backup > 10min stale): PagerDuty page on-call
3. **RTO approaching** (service down > 30min): PagerDuty page + manager escalation
4. **RTO exceeded** (service down > 1hr): Incident commander + status page update

## RTO/RPO Recovery Procedure

### RTO Recovery (Service Down)
1. Identify failure mode (see `ops/runbooks/full-outage.md`)
2. Execute appropriate runbook: DB failure → `db-saturation.md`, Redis failure → `redis-oom.md`
3. If infrastructure failure: execute blue/green swap → `docs/blue-green-deploy.md` rollback section
4. Verify restoration: `curl /api/v1/healthz`, `curl /api/v1/slo`
5. Post-recovery: document timeline, update RTO metric

### RPO Recovery (Data Loss Event)
1. Identify last valid backup timestamp
2. Stop all write traffic (connections draining via `ops/scripts/drain-connections.ps1`)
3. Restore from latest validated backup: follow `src/docs/runbooks/backup-restore.md`
4. Replay WAL segments from archive storage up to the failure point
5. Verify data integrity with `pg_restore -l` check
6. Resume write traffic gradually

## SLO Dashboard Integration

RTO/RPO metrics are displayed on the SLO dashboard (`workticket-slos.json`):
- **RTO Gauge**: Minutes since last full outage (green < 30, yellow < 60, red >= 60)
- **RPO Stat**: Seconds since last successful backup
- **Backup Verification**: Pass/fail status of latest restore test

## Testing
- **RTO drill**: Quarterly full-outage simulation (see `ops/runbooks/chaos-testing.md`)
- **RPO drill**: Monthly restore-from-backup verification
- **Cross-region restore**: Annual (validates R2/S3 archive integrity)
