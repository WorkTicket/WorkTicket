# Celery Worker Autoscaling Runbook

## Overview

Celery workers support two autoscaling modes:

1. **Kubernetes HPA** (recommended for production) — HorizontalPodAutoscaler
   based on CPU/memory utilization and custom queue-depth metrics.
2. **Docker Swarm + Python Autoscaler** — Python script that monitors
   Redis queue depth and scales service replicas via Docker API.

## Kubernetes HPA

### Prerequisites
- Prometheus Adapter installed in cluster
- Custom metric `celery_queue_depth_{queue}` exposed via Prometheus
- HPA manifests applied: `kubectl apply -f ops/k8s/hpa-celery.yaml`

### HPA Configuration

| Queue       | Min | Max | Scale-Out | Scale-In | Metric              |
|------------|-----|-----|-----------|----------|---------------------|
| ai_text    | 2   | 10  | +2/60s    | -1/120s  | CPU >70% OR depth>10 |
| ai_image   | 2   | 8   | +2/60s    | -1/120s  | CPU >70% OR depth>10 |
| ai_audio   | 2   | 6   | +2/60s    | -1/120s  | CPU >70% OR depth>10 |
| default    | 1   | 5   | +1/60s    | -1/180s  | CPU >70% OR depth>20 |

### Tuning
- Increase `stabilizationWindowSeconds` if scaling is too aggressive
- Decrease `averageValue` thresholds to scale earlier on queue buildup
- Monitor HPA decisions: `kubectl describe hpa celery-worker-text-hpa`

## Docker Swarm Autoscaler

### Running the Autoscaler
```bash
# Run as a one-shot check:
python ops/scripts/celery_autoscaler.py --once --dry-run

# Run continuously as a sidecar:
python ops/scripts/celery_autoscaler.py --interval 30

# Emit Prometheus metrics for monitoring:
python ops/scripts/celery_autoscaler.py --emit-metrics
```

### Environment Variables
```
CELERY_AUTOSCALE_INTERVAL=30        # Check interval in seconds
CELERY_AUTOSCALE_DRY_RUN=false      # Dry-run mode
CELERY_TEXT_MIN_REPLICAS=2           # Min replicas for ai_text
CELERY_TEXT_MAX_REPLICAS=10          # Max replicas for ai_text
CELERY_IMAGE_MIN_REPLICAS=2          # Min replicas for ai_image
CELERY_IMAGE_MAX_REPLICAS=8          # Max replicas for ai_image
CELERY_AUDIO_MIN_REPLICAS=2          # Min replicas for ai_audio
CELERY_AUDIO_MAX_REPLICAS=6          # Max replicas for ai_audio
CELERY_DEFAULT_MIN_REPLICAS=1        # Min replicas for default
CELERY_DEFAULT_MAX_REPLICAS=5        # Max replicas for default
```

### Docker Compose Integration
```bash
# Deploy with autoscale config:
docker compose -f docker-compose.yml -f docker-compose.autoscale.yml up -d
```

## Scaling Decisions

The autoscaler uses these queue depth thresholds:

| Depth    | Action            |
|----------|-------------------|
| 0-10     | Minimum replicas  |
| 11-50    | Min + 1 replicas  |
| 51-100   | Mid-range         |
| 101+     | Maximum replicas  |

## Monitoring Autoscaling

### Prometheus Metrics
- `celery_autoscaler_desired_replicas{queue,current}` — Desired replica count
- `celery_queue_depth{queue}` — Current queue depth
- `workticket_queue_depth` — Application-level queue monitoring

### Grafana Dashboard
- Autoscaling decisions visible in the Production Readiness dashboard
- Look for the "Worker Replicas" and "Queue Depth" panels

## Troubleshooting

### HPA Not Scaling
1. Check metrics server: `kubectl get hpa celery-worker-text-hpa -o yaml`
2. Verify custom metrics: `kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1`
3. Check Prometheus adapter logs

### Autoscaler Script Not Scaling
1. Verify Redis connectivity: `redis-cli PING`
2. Check queue depths: `redis-cli LLEN ai_text`
3. Run in dry-run mode first: `python ops/scripts/celery_autoscaler.py --once --dry-run`
4. Verify Docker Swarm access: `docker service ls`

## Rollback
- To disable autoscaling, set all min=max replicas
- For HPA: `kubectl delete hpa celery-worker-text-hpa`
- For Swarm: Stop the autoscaler sidecar container
