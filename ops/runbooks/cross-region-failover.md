# Cross-Region Disaster Recovery & Failover Runbook

## Overview

This runbook covers failover procedures for a multi-region deployment.
Currently the system runs in a single region. This document defines the
architecture and steps to add cross-region disaster recovery.

## Current Architecture
- **Single region** — all services in one AWS/GCP/Azure region
- **Cloudflare R2** — multi-region by default (automatic replication)
- **PostgreSQL** — single primary, no read replicas in secondary region
- **Redis** — single-region with Sentinel HA (not cross-region)

## Target Architecture (Cross-Region HA)

```
Primary Region (us-east-1)          Secondary Region (us-west-2)
┌─────────────────────────┐        ┌─────────────────────────┐
│  FastAPI (3+ replicas)  │        │  FastAPI (3+ replicas)  │
│  Celery Workers         │        │  Celery Workers         │
│  PostgreSQL Primary     │◄──WAL──│  PostgreSQL Replica     │
│  Redis Sentinel Cluster │        │  Redis Sentinel Cluster │
│  Ollama AI              │        │  Ollama AI              │
└─────────┬───────────────┘        └──────────┬──────────────┘
          │                                   │
          └──────────┬───────────┬────────────┘
                     │           │
              Cloudflare DNS     Cloudflare R2
              (Geo-routing)      (Replicated)
```

## Prerequisites for Cross-Region Setup

### Database
1. Enable WAL archiving in secondary region
2. Configure streaming replication: `pg_basebackup` to seed replica
3. Create `recovery.conf` with `primary_conninfo` pointing to primary
4. Monitor replication lag via `workticket_read_replica_lag_seconds`

### Redis
1. Deploy Redis Sentinel cluster in each region (3 nodes per region)
2. Sentinels monitor cross-region network health
3. On primary region failure, promote secondary Sentinel leader
4. Update `docker-compose.redis-ha.yml` with cross-region sentinel hosts

### Application
1. Deploy FastAPI + Celery workers in both regions
2. Use Cloudflare DNS geo-routing for traffic distribution
3. Both regions read from same R2 bucket (multi-region by default)
4. WebSocket connections re-establish on failover

## Failover Triggers

| Condition | Action | RTO |
|-----------|--------|-----|
| PostgreSQL primary down > 5min | Promote replica in secondary | 15 min |
| Primary region network outage | DNS failover to secondary | 5 min |
| Cluster-wide DB corruption | Point-in-time recovery | 2 hours |
| Cloudflare R2 outage | Read from secondary bucket | Automatic |

## Failover Procedure

### Step 1: Detect and Assess
```bash
# Check overall health
curl -s https://api.workticket.app/healthz | jq .

# Check DB replication status (primary)
psql -c "SELECT pg_is_in_recovery(), pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();"

# Check DB lag (secondary)
psql -c "SELECT EXTRACT(EPOCH FROM now() - pg_last_xact_replay_timestamp()) AS lag_seconds;"
```

### Step 2: Promote Secondary Database
```bash
# On secondary region DB server:
# 1. Stop replication
sudo systemctl stop postgresql

# 2. Promote to primary
sudo -u postgres pg_ctl promote -D /var/lib/postgresql/data

# 3. Verify primary status
psql -c "SELECT pg_is_in_recovery();"
# Should return: f (false = not in recovery = primary)

# 4. Update application config to point to new primary
```

### Step 3: Update DNS Routing
```bash
# Use Cloudflare API to update DNS records:
# Change from primary-region LB to secondary-region LB

curl -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"A","name":"api.workticket.app","content":"<secondary-lb-ip>","ttl":60}'
```

### Step 4: Restart Services in Secondary Region
```bash
# Update Kubernetes config with new DB endpoint
kubectl set env deployment/workticket-api DATABASE_URL=postgresql+asyncpg://<new-primary>:5432/workticket

# Roll restart
kubectl rollout restart deployment/workticket-api
kubectl rollout restart deployment/celery-worker-text
kubectl rollout restart deployment/celery-worker-image
kubectl rollout restart deployment/celery-worker-audio
kubectl rollout restart deployment/celery-worker-default
```

### Step 5: Verify Recovery
```bash
# Check health endpoints
curl -s https://api.workticket.app/healthz
curl -s https://api.workticket.app/readyz

# Check that AI is processing
curl -s https://api.workticket.app/readyz | jq '.components.ai'

# Verify billing webhook reception
# Check Stripe dashboard for successful webhook deliveries
```

## Recovery Objectives

| Tier | RTO | RPO | Description |
|------|-----|-----|-------------|
| Critical | < 15 min | < 5 min | Auto-failover DB + DNS |
| High | < 1 hour | < 15 min | Full region recovery |
| Medium | < 4 hours | < 1 hour | Disaster recovery from backups |

## Regular Testing

### Monthly Schedule
1. **Read-replica failover test**: Promote replica, verify, re-sync
2. **DNS routing test**: Update DNS, verify traffic shifts
3. **Full recovery drill**: Simulate primary region loss, verify recovery

### Test Commands
```bash
# Simulate replica promotion (non-destructive)
python ops/scripts/failover.py --validate-only

# Full failover drill (requires secondary region to be deployed)
python ops/scripts/failover.py --dry-run

# Recovery drill
python ops/scripts/failover.py --recovery-drill
```
