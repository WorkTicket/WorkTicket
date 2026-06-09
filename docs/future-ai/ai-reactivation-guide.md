# AI Reactivation Guide

Step-by-step checklist to re-enable AI in WorkTicket after MVP validation.

---

## Prerequisites

Before re-enabling AI, you must have:

- [ ] Paying customers validated
- [ ] Product-market fit confirmed
- [ ] Revenue stream established
- [ ] AI infrastructure provisioned (cloud or self-hosted)
- [ ] Budget approved for AI compute costs

---

## Phase 1: Infrastructure Provisioning

### Option A: Local AI (Ollama + Whisper)

```bash
# Start AI services with Docker profile
cd src
docker compose --profile ai up -d

# Wait for Ollama to pull models (2-5 minutes first time)
docker compose logs -f ollama
```

Hardware requirements:
- Ollama: 4 GB RAM minimum (8 GB recommended for larger models)
- Whisper: 2 GB RAM minimum
- GPU recommended but not required (CPU inference will be slow)

### Option B: Cloud AI

If switching to cloud AI (OpenAI, Anthropic, etc.):

1. Provision API keys from the chosen provider
2. Create a new `CloudAIService` implementation extending `AIService` base class
3. Update `.env` with API keys and endpoints
4. Update `orchestrator.py` to route to cloud service

---

## Phase 2: Configuration

### Enable AI

```bash
# In src/backend/.env or environment:
AI_DISABLED=false

# Or via feature flag:
FEATURE_AI_DISABLED=false
```

### Configure Models

```bash
# Ollama models (local)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_TEXT_MODEL=llama3.1:8b-q4_0
OLLAMA_VISION_MODEL=llama3.2-vision:11b-q4_0

# Whisper (local)
WHISPER_SERVICE_URL=http://whisper-service:8001
WHISPER_MODEL_SIZE=base
```

### Rate Limits (per plan)

```bash
RL_FREE_AI_RATE=0.5
RL_PRO_AI_RATE=2.0
RL_ENTERPRISE_AI_RATE=10.0
```

---

## Phase 3: Staging Validation

1. **Start staging environment with AI enabled:**
   ```bash
   docker compose --profile ai up -d
   ```

2. **Verify AI health check:**
   ```bash
   curl http://localhost:8000/health
   # Should show ollama_available: true, whisper_available: true
   ```

3. **Test AI endpoints:**
   ```bash
   # Submit a test job for AI processing
   curl -X POST http://localhost:8000/api/v1/ai/process-job/{job_id} \
     -H "Authorization: Bearer $TOKEN"

   # Check AI output
   curl http://localhost:8000/api/v1/ai/output/{job_id} \
     -H "Authorization: Bearer $TOKEN"
   ```

4. **Verify Celery workers:**
   ```bash
   docker compose logs celery-worker-default | grep "AI pipeline"
   ```

5. **Run AI-specific tests:**
   ```bash
   cd src/backend
   pytest tests/ -k "ai" -v
   ```

6. **Load testing:**
   ```bash
   # Run AI-specific load tests
   cd src/scripts
   python load_test.py --ai
   ```

7. **Cost estimation:**
   ```bash
   # Monitor ACU consumption
   curl http://localhost:8000/api/v1/ai/metrics/costs \
     -H "Authorization: Bearer $TOKEN"
   ```

---

## Phase 4: Production Rollout

### 4.1 Enable in Production

```bash
# Set environment variable in production
AI_DISABLED=false

# Or via Redis feature flag (no restart needed):
redis-cli SETEX feature_flag:global:ai_disabled 2592000 "0"
```

### 4.2 Start AI Services

```bash
docker compose --profile ai up -d
```

### 4.3 Monitor

Watch these key metrics for first 24 hours:

| Metric | Dashboard | Alert Threshold |
|---|---|---|
| AI failure rate | `/api/v1/ai/metrics` | > 5% |
| Ollama response time | Grafana: AI Circuit | > 30s p99 |
| Whisper latency | Grafana: Whisper | > 60s p95 |
| ACU consumption | Billing dashboard | Per-plan limits |
| Worker queue depth | Celery Flower | > 100 pending |
| Cost per job | `/api/v1/ai/metrics/costs` | Budget alert |

### 4.4 Rollback if Needed

```bash
# Disable AI immediately:
redis-cli SETEX feature_flag:global:ai_disabled 2592000 "1"

# Stop AI services:
docker compose --profile ai down
```

---

## Phase 5: Post-Rollout

- [ ] Monitor error rates for 1 week
- [ ] Track cost vs. budget
- [ ] Gather user feedback on AI quality
- [ ] Tune models based on feedback
- [ ] Optimize prompts
- [ ] Review rate limits

---

## Reactivation Verification Checklist

| # | Step | Status |
|---|---|---|
| 1 | AI infrastructure provisioned | [ ] |
| 2 | Environment variables configured | [ ] |
| 3 | AI services started | [ ] |
| 4 | Backend AI health check passes | [ ] |
| 5 | AI endpoints return 200 | [ ] |
| 6 | Celery AI tasks execute | [ ] |
| 7 | WebSocket job status works | [ ] |
| 8 | AI output stored in DB | [ ] |
| 9 | Billing/ACU tracking works | [ ] |
| 10 | All AI tests pass | [ ] |
| 11 | Load testing complete | [ ] |
| 12 | Cost within budget | [ ] |
| 13 | Frontend AI features visible | [ ] |
