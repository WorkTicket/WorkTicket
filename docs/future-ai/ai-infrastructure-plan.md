# AI Infrastructure Plan

Infrastructure requirements for AI reactivation in WorkTicket.

---

## Current Infrastructure (Dormant)

### Local AI (Ollama + Whisper)

| Service | Container | Resources | Network |
|---|---|---|---|
| Ollama | `ollama/ollama:0.6.0` | 4 GB RAM, GPU optional | `ai-internal` |
| Whisper STT | Custom Dockerfile | 2 GB RAM | `ai-internal` |
| Celery Text Worker | Custom Dockerfile | 1 GB RAM x3 | Docker networks |
| Celery Image Worker | Custom Dockerfile | 1 GB RAM x3 | Docker networks |
| Celery Audio Worker | Custom Dockerfile | 1 GB RAM x3 | Docker networks |
| pgvector | `pgvector/pgvector:pg16` | 1 GB RAM | `backend-db` (shared) |

### Total Resource Requirements (MVP AI)

```
Base (non-AI):   ~6 GB RAM  (postgres, redis, backend, nginx, workers)
AI overlay:      ~10 GB RAM (ollama 4G + whisper 2G + 4 workers x 1G)
Total:           ~16 GB RAM minimum for full AI stack
```

---

## Option A: Cloud AI Providers

### Cost Comparison (Estimated Monthly)

| Provider | Text Model | Vision Model | Audio Model | Est. Cost (50 jobs/day) |
|---|---|---|---|---|
| OpenAI | GPT-4o-mini | GPT-4o | Whisper API | $150-300/mo |
| Anthropic | Claude Haiku | Claude Sonnet | N/A | $200-400/mo |
| Google | Gemini Flash | Gemini Pro | Chirp | $100-250/mo |
| Groq | Llama 3 70B | N/A | Whisper | $50-150/mo |
| Together AI | Llama 3.1 70B | Llama 3.2 Vision | N/A | $80-200/mo |

### Integration Steps

1. Create cloud service classes extending `AIService` abstract base
2. Add API key configuration to Settings
3. Update orchestrator to route to cloud services
4. Test with staging environment
5. Update rate limits and cost tracking

---

## Option B: Self-Hosted AI

### Minimum Hardware Spec

```
CPU: 16 cores (modern x86_64)
RAM: 32 GB (16 GB for AI models + 16 GB for application)
GPU: Single NVIDIA RTX 4060 Ti (16 GB VRAM) or better
Storage: 100 GB SSD for models
```

### Recommended Hardware Spec

```
CPU: 32 cores
RAM: 64 GB
GPU: Dual NVIDIA RTX 4090 (24 GB VRAM each)
Storage: 500 GB NVMe for models + data
```

### Self-Hosted Software Stack

| Component | Software | Purpose |
|---|---|---|
| LLM Server | Ollama or vLLM | Model hosting and inference |
| Model(s) | Llama 3.1 70B (text) + Llama 3.2 Vision | Generation |
| STT | faster-whisper (large-v3) | Speech-to-text |
| Vector DB | pgvector (already deployed) | Embeddings and RAG |
| GPU Orchestration | NVIDIA Docker runtime | GPU access from containers |

### Docker GPU Configuration

```yaml
# docker-compose AI overlay (gpu profile)
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]
```

---

## A/B Deployment Strategy

When reactivating AI, consider a gradual rollout:

1. **Phase 1**: Enable AI for 5% of users (canary)
2. **Phase 2**: Monitor for 48 hours
3. **Phase 3**: Expand to 25%, then 50%, then 100%
4. **Rollback trigger**: Error rate > 5% or cost > budget

Feature flags support per-company overrides, enabling this strategy:
```bash
# Enable AI for specific company
redis-cli SETEX feature_flag:company:{company_id}:ai_disabled 2592000 "0"
```

---

## Monitoring Infrastructure

When AI is active, monitor:

| Metric | Source | Alert |
|---|---|---|
| AI job success rate | Prometheus | < 95% |
| Ollama latency (p99) | Prometheus | > 30s |
| Whisper latency (p95) | Prometheus | > 60s |
| Circuit breaker trips | Grafana | > 3/hour |
| ACU consumption rate | Billing DB | > daily budget |
| Worker queue depth | Celery Flower | > 200 |
| GPU utilization | nvidia-smi | > 90% sustained |
| Prompt injection attempts | Audit log | Any detected |
