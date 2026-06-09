# AI Outage Runbook

## Detection
- Circuit breaker opens (LLM, Vision, or Whisper) — `AILlmCircuitOpen` / `AIWhisperCircuitOpen` alerts fire
- `/readyz` shows `ai_gateway` degraded
- AI outputs return `confidence=0.0`, `is_fallback=True`
- `AIFallbackResponses` Prometheus alert fires
- Jobs complete with no AI analysis

## Impact
- New AI processing will use fallback (no analysis, confidence=0.0)
- Existing in-flight jobs will complete with fallback output
- Historical AI data is unaffected
- Frontend will display "AI unavailable" banners
- Billing will not charge for fallback outputs (cost set to 0)

## Affected Components
| Component | Downstream Effect |
|-----------|------------------|
| Ollama (llama3.1:8b) | LLM text analysis unavailable |
| Ollama (llama3.2-vision:11b) | Image analysis unavailable |
| faster-whisper service | Audio transcription unavailable |
| Celery AI workers | Jobs complete without AI output |

## Investigation Steps

### 1. Check Circuit Breaker State
```bash
# Check Redis for circuit breaker keys
redis-cli -h <redis-host> GET "circuit:breaker:llm"
redis-cli -h <redis-host> GET "circuit:breaker:whisper"

# Or via API
curl <api>/readyz | jq .ai_gateway
```

### 2. Check AI Service Health
```bash
# Check Ollama
curl -f http://ollama:11434/api/tags

# Check Whisper service
curl -f http://whisper-service:9000/health

# Check container logs
docker logs --tail=100 <ollama-container>
docker logs --tail=100 <whisper-container>
```

### 3. Check Resource Usage
```bash
# Ollama memory/GPU usage
docker stats <ollama-container>

# Whisper service
docker stats <whisper-container>

# Check for OOM kills
dmesg | grep -i "oom\|killed"
```

### 4. Check Celery Worker Logs
```bash
# AI worker logs (check for connection errors)
kubectl logs -l app=celery-worker-ai --tail=200
```

## Recovery Steps

### Automatic Recovery
1. **Circuit breaker half-open probe:** After 120s cooldown, exactly 1 probe request is allowed globally across all replicas
2. **Success on probe:** Circuit closes automatically, normal AI processing resumes
3. **Failure on probe:** Circuit reopens, cooldown doubles (exponential backoff: 120s → 240s → 480s, max 300s)

### Manual Recovery
1. **Restart Ollama:**
   ```bash
   kubectl rollout restart deployment/ollama
   # or
   docker-compose restart ollama
   ```

2. **Restart Whisper service:**
   ```bash
   kubectl rollout restart deployment/whisper-service
   # or
   docker-compose restart whisper-service
   ```

3. **Reset circuit breakers manually (if needed):**
   ```bash
   redis-cli DEL "circuit:breaker:llm"
   redis-cli DEL "circuit:breaker:whisper"
   ```

4. **Verify recovery:**
   ```bash
   curl <api>/readyz | jq .ai_gateway
   # Should show: "status": "healthy"
   ```

## Graceful Degradation Behavior
- **LLM down:** Audio transcription and image analysis still work independently
- **Whisper down:** Text and image analysis still work, audio is skipped
- **Vision down:** Text analysis still works, images analyzed without visual context
- **All AI down:** Jobs complete with `is_fallback=True`, `confidence=0.0`, no billing charge
- **Partial pipeline:** Each AI step has its own circuit breaker — failures are independent

## Post-Recovery Verification
1. Submit a test job via API
2. Verify AI output has `is_fallback=False` and `confidence > 0.0`
3. Verify billing correctly charges for resumed AI usage
4. Monitor `AIFallbackResponses` metric — should drop to 0

## Escalation
| Duration | Action |
|----------|--------|
| > 15 min | Notify on-call engineer |
| > 1 hour | Engineering lead |
| > 4 hours | CTO — consider manual invoice generation |
| Data corruption suspected | CTO + security team immediately |

## Related Runbooks
- `stuck-jobs.md` — for jobs stuck in processing during AI outage
- `worker-stuck.md` — if Celery AI workers are the root cause
- `acu-debt-reconciliation.md` — if billing discrepancy from fallback outputs
