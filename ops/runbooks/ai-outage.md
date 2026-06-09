# AI Provider Outage Runbook

## Detection
- Alert: `workticket_ai_fallback_total` > 0 over 2m
- Alert: `workticket_ai_gateway_llm_circuit == 1`, `_vision_circuit`, `_whisper_circuit`
- Symptom: AI outputs returned with `confidence=0.0`, `is_fallback=true`
- Symptom: `/readyz` shows AI component status = degraded

## Triage
1. Check circuit breaker state on `/readyz`:
   - `llm_circuit_open`, `vision_circuit_open`, `whisper_circuit_open`
2. Check Ollama health: `curl http://<ollama-host>:11434/api/health`
3. Check Whisper health: `curl http://<whisper-host>:8001/health`
4. Check AI gateway logs for timeout/connection errors
5. Verify Ollama model availability: `ollama list`

## Circuit Breaker Behavior
- **Trigger:** 3 consecutive failures → 120s cooldown
- **Recovery:** Auto half-open probe after cooldown expiry
- **Fallback:** `_llm_fallback()` returns structured response with `ai_unavailable` indicator
- **Partial pipeline:** Audio/vision/text steps are independent; one failing does not block others

## Graceful Degradation Modes

### LLM (Text) Outage
- Vision and Whisper continue to process
- Jobs requiring text analysis return `ai_unavailable`
- `AIOutputSchema.confidence = 0.0` for affected outputs

### Vision Outage
- Text and Whisper continue normally
- Image-based jobs skip vision step
- Photos are still uploaded and stored

### Whisper Outage
- Text and Vision continue normally
- Audio files are still uploaded and stored
- Transcription requests are queued until recovery

### Complete AI Outage
- All AI processing returns fallback responses
- Non-AI workflow (job creation, media upload, billing) continues unaffected
- Consider setting `ai_disabled` flag on `BillingAccount` for administrative disable

## Recovery Procedure
1. Wait for circuit breaker auto-recovery (120s cooldown)
2. Or force-reset circuit breaker via Redis:
   ```bash
   redis-cli DEL "ai:circuit:llm"
   redis-cli DEL "ai:circuit:vision"
   redis-cli DEL "ai:circuit:whisper"
   ```
3. Verify recovery on `/readyz`
4. Check stalled jobs: `scan_for_stalled_ai_jobs` beat task (runs every 5 min)
5. Monitor `workticket_ai_fallback_total` for return to normal

## Stalled Job Recovery
- `scan_for_stalled_ai_jobs` beat task runs every 5 minutes
- Jobs stuck in `processing` state for >5 min are re-queued
- After 3 re-queue attempts, job is moved to dead letter queue
- `recover_orphaned_outputs` runs every 6h to clean up partial outputs

## Prevention
- Circuit breakers prevent retry amplification during prolonged outage
- Per-queue backpressure limits cap AI task queue depth
- ACU quota system prevents runaway AI usage
- Three independent circuit breakers (LLM, Vision, Whisper) isolate failures
