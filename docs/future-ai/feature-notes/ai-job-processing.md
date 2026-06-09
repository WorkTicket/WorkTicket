# Feature Note: AI Job Processing Pipeline

## Component Information

- **Name:** AI Job Processing Pipeline
- **Files:** 
  - `src/backend/tasks/job_tasks.py` (`process_job_task`)
  - `src/backend/app/ai/gateway.py` (`AIGateway`)
  - `src/backend/app/ai/orchestrator.py` (`AIOrchestrator`)
  - `src/backend/app/ai/router.py` (API endpoints)
- **Dependencies:** Ollama, Whisper Service, Redis, PostgreSQL
- **Env Vars:** `AI_DISABLED`, `OLLAMA_BASE_URL`, `WHISPER_SERVICE_URL`, `CELERY_TASK_SIGNING_KEY`
- **Infrastructure:** Celery workers (text, image, audio), Ollama server, Whisper service

## Current Status

The AI job processing pipeline is the core AI workflow. Users create jobs with text descriptions, images, and/or audio recordings. The pipeline:
1. Validates the request (auth, rate limiting, quota)
2. Routes to the appropriate AI service (text generation, image analysis, audio transcription)
3. Generates structured output (problem type, summary, recommended fix, materials, estimated hours, confidence)
4. Stores the result and reconciles billing

**Production Readiness:** Beta — fully implemented with comprehensive error handling
**Known Issues:** None blocking
**Technical Debt:** WebSocket scalability for high connection counts

## Reactivation Plan

1. Set `AI_DISABLED=false` in environment
2. Start AI services: `docker compose --profile ai up -d`
3. Verify: `POST /api/v1/ai/process-job/{id}` returns 200
4. Monitor Celery workers for successful completion

## Architecture Notes

The pipeline uses a 3-phase approach:
- Phase 1: Pre-AI (quota reservation, Redis lock, state transition)
- Phase 2: AI Gateway (orchestration, circuit breaker, output validation)
- Phase 3: Post-AI (storage, cost reconciliation, state completion)
