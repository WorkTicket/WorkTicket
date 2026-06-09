# AI Architecture

WorkTicket AI architecture overview — design intent, data flow, and service interactions.

---

## Design Philosophy

WorkTicket AI is architected as a **local-only** system (ADR-002) to:
- Eliminate external API costs during development
- Protect user data (no data leaves the deployment)
- Enable offline-capable field service scenarios
- Allow easy migration to cloud AI when scale demands it

The architecture uses a **gateway pattern** with circuit breakers, concurrency control, and comprehensive prompt injection defense.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                      Frontend Layer                       │
│  Web Dashboard (Next.js)    │    Mobile App (React Native)│
│  AI Section (hidden in v1)  │    AI hidden in v1          │
└─────────────┬────────────────────┬───────────────────────┘
              │                    │
              ▼                    ▼
┌──────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                   │
│                                                          │
│  POST /api/v1/ai/process-job/{id}  ◄── AI Router          │
│  GET  /api/v1/ai/output/{id}                              │
│  GET  /api/v1/ai/metrics                                  │
│  WS   /api/v1/ai/ws/job-status/{id}                      │
│                                                          │
│  ┌──────────────────────────────────────┐                │
│  │         AIGateway (gateway.py)       │                │
│  │  ┌──────────┐  ┌──────────────────┐  │                │
│  │  │ Circuit  │  │  Concurrency     │  │                │
│  │  │ Breaker  │  │  Limiter         │  │                │
│  │  └──────────┘  └──────────────────┘  │                │
│  │  ┌────────────────────────────────┐  │                │
│  │  │  Prompt Injection Defense      │  │                │
│  │  │  - Input sanitization          │  │                │
│  │  │  - Unicode normalization       │  │                │
│  │  │  - Semantic risk scoring       │  │                │
│  │  │  - Shingle similarity detect   │  │                │
│  │  │  - Prompt leakage detection    │  │                │
│  │  └────────────────────────────────┘  │                │
│  └──────────────┬───────────────────────┘                │
│                 │                                         │
│  ┌──────────────▼───────────────────────┐                │
│  │     AIOrchestrator (orchestrator.py)  │                │
│  │  Routes to correct service based on   │                │
│  │  content type (text/image/audio)      │                │
│  └──────┬───────────────────────┬───────┘                │
└─────────┼───────────────────────┼────────────────────────┘
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  OllamaService   │    │  WhisperService  │
│  (ollama)        │    │  (whisper)       │
│                  │    │                  │
│  Text: llama3.1  │    │  faster-whisper  │
│  Img: llama3.2   │    │  base model      │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Ollama Server   │    │  Whisper Service │
│  (ollama:11434)  │    │  (whisper:8001)  │
└──────────────────┘    └──────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────┐
│                  Async Processing (Celery)                 │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │
│  │ ai_text queue  │  │ ai_image queue │  │ai_audio q   │ │
│  │ Worker x3      │  │ Worker x3      │  │ Worker x3   │ │
│  └───────┬────────┘  └───────┬────────┘  └──────┬─────┘ │
│          │                   │                   │       │
│  ┌───────▼───────────────────▼───────────────────▼─────┐ │
│  │              default queue                          │ │
│  │  process_job_task (3-phase pipeline)                │ │
│  │  Phase 1: Pre-AI (quota, state, lock)              │ │
│  │  Phase 2: AI Gateway (orchestrate)                 │ │
│  │  Phase 3: Post-AI (store, reconcile, complete)     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Dead Letter Queue (DLQ) — failed tasks, retry, poison   │
│  Beat Scheduler — stalled job scanning (5min)            │
└──────────────────────────────────────────────────────────┘
```

---

## Key Components

### AIGateway (`gateway.py`)

Central coordinator that:
1. Validates and sanitizes all inputs before AI processing
2. Manages circuit breakers (Redis-backed) for LLM, vision, and whisper
3. Enforces concurrency limits per-company
4. Performs prompt injection defense
5. Runs output sanitization/validation

### AIOrchestrator (`orchestrator.py`)

Routes requests to appropriate service:
- Text-only jobs → OllamaService (text model)
- Jobs with images → OllamaService (vision model)
- Jobs with audio → WhisperService (STT)

### Circuit Breaker (`circuit_breaker.py`)

- Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (probing)
- Redis-backed for global coordination across replicas
- Uses Lua scripts for atomic half-open probes
- Auto-recovers when services become healthy

### Concurrency Limiter (`concurrency.py`)

- Per-company limits to prevent resource exhaustion
- Redis-backed with TTL-based lock expiry
- Falls back to local limiting when Redis unavailable

---

## Data Flow: AI Job Processing

```
1. User creates job with media (text/audio/images)
2. Frontend calls POST /api/v1/ai/process-job/{id}
3. API validates:
   - Authentication + rate limiting
   - Job exists and belongs to company
   - Daily spend within limits
   - Company concurrency available
   - Abuse risk score check
4. Job state transitions: none → queued
5. Task enqueued to Celery default queue
6. Celery worker picks up process_job_task:

   Phase 1 (Pre-AI):
   - Redis lock acquired (prevents duplicate processing)
   - Quota check + reservation (FOR UPDATE row lock)
   - State transition: queued → reserved → processing

   Phase 2 (AI Gateway):
   - AIGateway orchestrates text/audio/image processing
   - Output validated against schema
   - Confidence scored

   Phase 3 (Post-AI):
   - Output stored in ai_output table
   - Cost reconciled against reservation
   - State transition: processing → completed
   - Redis pub/sub notifies WebSocket subscribers
   - Concurrency released
   - Lock released

7. WebSocket streams status updates to frontend
8. Frontend displays AI-generated estimate/summary
```

---

## Security Architecture

### Prompt Injection Defense

1. **Input Sanitization**: XML escaping, special token removal, instruction override pattern detection
2. **Semantic Risk Scoring**: Detects prompt injection patterns in input
3. **Shingle Similarity**: Detects novel injection patterns via n-gram analysis
4. **Prompt Leakage Detection**: Blocks output containing system prompt fragments
5. **Unicode Confusable Normalization**: Prevents homoglyph attacks

### HMAC Task Signing

All Celery AI tasks are HMAC-signed using `CELERY_TASK_SIGNING_KEY`. Workers verify signatures before executing. Unsigned or tampered tasks are sent to DLQ.

### SSRF Protection

AI media downloads are validated against `allowed_hosts` to prevent SSRF attacks via crafted URLs.

---

## Scaling Considerations

### Current (Local AI)

- Single Ollama instance per deployment
- Limited by GPU/CPU availability
- Suitable for <50 concurrent AI jobs

### Future (Cloud AI)

- Horizontal scaling: multiple Ollama replicas with load balancing
- Queue-based scaling: add more Celery workers per queue
- Circuit breaker prevents cascading failures
- Can introduce cloud AI providers as alternative backends via the AIService abstract interface
