# Deployment Architecture

## Container Topology

```
                          ┌─────────────┐
                          │   Nginx     │
                          │  (Reverse   │
                          │   Proxy)    │
                          └──────┬──────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼───┐  ┌────▼────┐  ┌───▼──────┐
              │  API    │  │Dashboard│  │   Whisper │
              │ (FastAPI)│  │(Next.js)│  │  Service  │
              └────┬────┘  └─────────┘  └──────────┘
                   │
          ┌────────┼────────┐
          │        │        │
    ┌─────▼──┐ ┌──▼───┐  ┌─▼───────┐
    │ Celery │ │Redis │  │PostgreSQL│
    │Workers │ │      │  │  (PG16)  │
    └────────┘ └──────┘  └──────────┘
```

## Infrastructure Components

| Component | Scaling | Notes |
|---|---|---|
| API Server | Horizontal (multiple replicas) | Stateless, all state in DB/Redis |
| Celery Worker | Horizontal (per queue) | Separate queues for AI, billing, media, maintenance |
| Redis | Sentinel HA (3 nodes) | Broker, result backend, rate limiter, cache |
| PostgreSQL | Single primary + replicas | RLS enabled, pgvector extension |
| Nginx | Single / LB fronted | Rate limiting, TLS, static assets |

## Docker Compose (Local Development)

See `src/docker-compose.yml` for the full local development stack:
- All services with hot-reload mounts
- PostgreSQL 16 with pgvector
- Redis 7
- Minio (S3-compatible storage for R2 emulation)
- Mailpit (email testing)
- Ollama (optional, for AI features)

## Kubernetes (Production)

See `src/k8s/` for deployment manifests:
- `api-deployment.yaml` — FastAPI with HPA, resource limits, liveness probes
- `worker-deployments.yaml` — Celery workers per queue
- `kustomization.yaml` — Kustomize base for environment overlays

Operational HPA config at `ops/k8s/hpa-celery.yaml` for queue-depth-based autoscaling.

## Environment Variants

| Environment | Infrastructure | Data | AI |
|---|---|---|---|
| Codespaces | Docker Compose | Ephemeral PostgreSQL | Optional |
| Local Dev | Docker Compose | Local PostgreSQL | Optional |
| Staging | Docker Compose / K8s | Seeded test data | Enabled |
| Production | K8s | Managed PostgreSQL | Enabled |

## Deployment Sequence

1. Database migrations (`alembic upgrade head`)
2. Redis cluster health check
3. API server rollout (rolling update)
4. Celery worker rollout
5. Dashboard static build / deploy
6. Health check verification
7. Traffic switch

See `ops-guide.md` for detailed deployment procedures and rollback instructions.

## Monitoring & Alerting

- Prometheus metrics at `/metrics` (token-protected)
- SLO tracking via Grafana dashboards (`ops/grafana-dashboards/`)
- Alerting rules at `ops/prometheus-alerts/`
- Sentry for error tracking
- Synthetic monitoring for critical paths

## Backup & Recovery

- Automated PostgreSQL backups via `src/backend/scripts/backup.sh`
- Point-in-time recovery support
- R2 (Cloudflare) for durable media storage
- Restore procedure at `ops/runbooks/rto-rpo.md`
