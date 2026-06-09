# ADR 002: AI Local-Only Strategy

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket uses AI to analyze job descriptions, images, and audio recordings
to generate estimates, identify equipment, and summarize work orders. We needed
to choose between:

1. **Cloud LLM APIs** (OpenAI, Anthropic, Google) - pay-per-token pricing
2. **Self-hosted Ollama** - fixed infrastructure cost, local execution

## Decision

We chose **self-hosted Ollama** with llama3.1 (text) and llama3.2-vision
(models) and faster-whisper (audio transcription).

### Key factors:
1. **Data sovereignty**: Job descriptions, customer addresses, and trade
   secrets never leave our infrastructure
2. **Cost predictability**: Fixed GPU infrastructure cost vs. variable
   per-token billing
3. **Latency**: Local execution eliminates network round-trips
4. **No rate limits**: No API quota concerns for burst processing
5. **Offline capability**: AI works even without internet connectivity

## Consequences

### Positive
- Zero per-request AI cost
- Customer data stays within our infrastructure
- No third-party API dependency or rate limits
- Predictable infrastructure costs

### Negative
- **GPU infrastructure required**: Each server needs GPU(s) for inference
- **Model quality cap**: Local models may underperform cloud models on
  complex tasks
- **Scaling complexity**: GPU capacity must scale linearly with tenant count
- **Model management**: We own model updates, quantization, and optimization

### Circuit Breaker Protection
All AI calls go through a circuit breaker (3 failures → 120s cooldown)
with graceful fallback. When AI is unavailable, jobs receive an
`is_fallback=True` output with a clear "AI processing is currently
unavailable" message.

### Migration Path
If local models prove insufficient, the architecture supports plugging
in cloud LLM APIs with minimal code changes (the AI gateway already
abstracts the provider).
