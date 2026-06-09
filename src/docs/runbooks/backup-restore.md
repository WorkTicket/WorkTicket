# Runbook: Backup & Restore

## Automated Backup
- Celery beat task: `daily_db_backup` runs at 2:00 AM UTC
- PostgreSQL: `pg_dump -F c` → compressed dump
- Redis: RDB snapshot via `SAVE` command
- Both uploaded to S3/R2

## Manual Backup
```bash
# Full backup
PGPASSWORD=postgres pg_dump -h localhost -U postgres -d workticket -F c > backup_$(date +%Y%m%d).dump

# Redis
redis-cli SAVE
cp /data/dump.rdb redis_backup.rdb
```

## Restore
```bash
# PostgreSQL
pg_restore -h localhost -U postgres -d workticket --clean backup.dump

# Redis
redis-cli FLUSHALL
redis-cli --pipe < redis_backup.rdb
```

## Verification
1. Run `python scripts/chaos/db_exhaustion.py` after restore
2. Check `/health` endpoint returns 200
3. Verify a known user can authenticate
