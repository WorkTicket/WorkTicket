# AI Asset Inventory

Complete inventory of all AI-related components in the WorkTicket codebase.  
**Last updated:** 2026-06-08 | **AI Status:** DISABLED

---

## 1. AI Source Code Files

### Core AI Module (`src/backend/app/ai/`)

| File | Purpose | Reactivation Critical |
|---|---|---|
| `__init__.py` | Module init | No |
| `service.py` | Abstract base class `AIService` — defines `transcribe_audio()`, `analyze_images()`, `generate_structured_output()` | Yes |
| `ollama_service.py` | Ollama LLM integration (llama3.1 text, llama3.2-vision). Prompt sanitization, injection defense, JSON output parsing. | **Yes** |
| `whisper_service.py` | Whisper STT client — calls whisper-service microservice for audio transcription | **Yes** |
| `gateway.py` | `AIGateway` — central coordinator with circuit breakers, concurrency limiters, prompt injection defense, Unicode normalization | **Yes** |
| `orchestrator.py` | `AIOrchestrator` — routes between OllamaService and WhisperService. Provides `generate_chat_output()` | **Yes** |
| `router.py` | FastAPI router — REST endpoints for AI processing, WebSocket job status, feedback, metrics, anomaly detection | **Yes** |
| `schemas.py` | Pydantic schemas — `AIOutputSchema`, request/response models | Yes |
| `circuit_breaker.py` | Redis-backed circuit breaker with Lua scripts for coordinated half-open probes | Yes |
| `concurrency.py` | `ConcurrencyLimiter` — limits concurrent AI requests per-company | Yes |
| `rate_limiter.py` | Rate limiting for AI endpoints | Yes |
| `local_rate_limiter.py` | Local fallback rate limiter | No |
| `audit.py` | AI request audit logging | Yes |
| `business_metrics.py` | AI business metrics aggregation | No |
| `failure_classifier.py` | AI failure classification | No |
| `metrics.py` | AI operational metrics | No |
| `models.py` | AI ORM models (AIOutput, AIOutputFeedback) | Yes |
| `ssrf_validator.py` | SSRF validation for AI media URL downloads | Yes |
| `validator.py` | AI output validation logic (confidence thresholds, etc.) | Yes |

### Celery AI Tasks (`src/backend/tasks/`)

| File | Task | Queue | Purpose |
|---|---|---|---|
| `ai_tasks.py` | `process_ai_text` | `ai_text` | AI text generation via Ollama |
| `ai_tasks.py` | `process_ai_audio` | `ai_audio` | Audio transcription via Whisper |
| `ai_tasks.py` | `process_ai_image` | `ai_image` | Image analysis via Ollama Vision |
| `job_tasks.py` | `process_job_task` | `default` | Main 3-phase AI pipeline (pre-AI, AI gateway, post-AI) |
| `job_tasks.py` | `scan_for_stalled_ai_jobs` | `beat` | Recover stalled/lost AI jobs |

### AI-Related Celery Beat Tasks (`src/backend/celery_config/beat.py`)

| Beat Entry | Task | Interval | Purpose |
|---|---|---|---|
| `scan-for-stalled-ai-jobs` | `tasks.job_tasks.scan_for_stalled_ai_jobs` | 5 min | Recover jobs where Celery message was lost |
| `recover-orphaned-outputs-every-6-hours` | `tasks.maintenance.recover_orphaned_outputs` | 6 hr | Fix AIOutput without completed job state |
| `cleanup-old-estimates-daily` | `tasks.maintenance.cleanup_old_estimates` | 24 hr | Purge old AIJobEstimate records (>90 days) |

### AI Middleware (`src/backend/app/middleware/`)

| File | Purpose |
|---|---|
| `sanitize.py` | AI response sanitization middleware |
| `rate_limit.py` | Rate limiting (includes AI-specific rate limits per plan) |

### AI in Other Backend Modules

| File | AI Dependency |
|---|---|
| `app/main.py` | AI router inclusion, gateway health check at startup |
| `app/config.py` | Ollama + Whisper config, AI rate limits per plan, `ai_disabled` flag |
| `app/estimates/engine.py` | References AI schemas for estimate generation |
| `app/estimates/router.py` | Estimate routes linked to AI output |
| `app/quotes/router.py` | Quote routes linked to AI output |
| `app/billing/reconciliation.py` | Cost reconciliation for AI jobs |
| `app/billing/concurrency.py` | Per-company AI concurrency limits |
| `app/billing/abuse.py` | AI request abuse detection |
| `app/billing/routing_engine.py` | AI job routing |
| `app/billing/invoice_routes.py` | AI cost billing |
| `app/monitoring/prometheus.py` | AI-specific Prometheus metrics |
| `app/monitoring/anomaly.py` | AI output quality drift detection |

---

## 2. AI API Endpoints

All under prefix `/api/v1/ai`:

| Method | Path | Purpose | Guarded |
|---|---|---|---|
| POST | `/process-job/{job_id}` | Submit job for AI processing | Yes (`_require_ai_enabled()`) |
| GET | `/output/{job_id}` | Get AI output for a job | Yes |
| POST | `/feedback` | Submit AI output feedback | Yes |
| GET | `/metrics/business` | Business metrics for AI | Yes |
| GET | `/metrics/costs` | AI cost metrics | Yes |
| GET | `/metrics` | Operational AI metrics | Yes |
| GET | `/anomaly-check` | Anomaly detection on AI outputs | Yes |
| GET | `/failures/classification` | AI failure classification | Yes |
| WS | `/ws/job-status/{job_id}` | WebSocket for AI job status streaming | Yes |

---

## 3. AI Worker Jobs (Celery)

### AI-Specific Worker Containers (Docker `ai` profile)

| Service | Queue | Concurrency | Purpose |
|---|---|---|---|
| `celery-worker-text` | `ai_text` | 3 | AI text generation |
| `celery-worker-image` | `ai_image` | 3 | Image analysis (vision) |
| `celery-worker-audio` | `ai_audio` | 3 | Audio transcription |

### Default Worker (always runs)

| Service | Queue | Concurrency | AI Task |
|---|---|---|---|
| `celery-worker-default` | `default` | 2 | `process_job_task` (includes AI pipeline) |

### Beat Worker (always runs)

| Service | Queue | Concurrency | AI Tasks |
|---|---|---|---|
| `celery-worker-beat` | `beat` | 1 | `scan_for_stalled_ai_jobs`, `recover_orphaned_outputs`, `cleanup_old_estimates` |

---

## 4. AI Database Tables

| Table | Model | Migration | Purpose |
|---|---|---|---|
| `ai_output` | `AIOutput` | `001_initial_schema` | Stores AI-generated outputs (JSON result, confidence, model used) |
| `ai_output_company_job_created` | Index | `019_add_ai_output_company_job_created_index` | Query performance index |
| `ai_disabled_reason` | Column | `024_add_ai_disabled_reason` | Per-company AI disable reason |
| `ai_output_feedback` | `AIOutputFeedback` | `032_add_company_id_to_ai_output_feedback` | User feedback on AI outputs |
| `ai_job_estimate` | `AIJobEstimate` | `026_add_ai_job_estimate_unique_and_indexes` | AI-generated cost estimates |

---

## 5. AI Environment Variables

### Ollama

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TEXT_MODEL` | `llama3.1:8b-q4_0` | Text generation model |
| `OLLAMA_VISION_MODEL` | `llama3.2-vision:11b-q4_0` | Vision model |
| `OLLAMA_TIMEOUT` | `300` | Request timeout (seconds) |

### Whisper

| Variable | Default | Purpose |
|---|---|---|
| `WHISPER_SERVICE_URL` | `http://localhost:8001` | Whisper service URL |
| `WHISPER_MODEL_SIZE` | `base` | STT model size |
| `WHISPER_API_KEY` | (empty) | API key for whisper service |

### Feature Flags

| Variable | Default | Purpose |
|---|---|---|
| `AI_DISABLED` | `true` | Master AI kill switch |
| `FEATURE_AI_DISABLED` | `true` | Feature flag override |
| `FEATURE_AI_CELERY_ASYNC` | `true` | Async vs sync Celery dispatch |

### Rate Limits (per plan)

| Variable | Default | Purpose |
|---|---|---|
| `RL_FREE_AI_RATE` | `0.5` | Free plan AI tokens/sec |
| `RL_PRO_AI_RATE` | `2.0` | Pro plan AI tokens/sec |
| `RL_ENTERPRISE_AI_RATE` | `10.0` | Enterprise plan AI tokens/sec |

---

## 6. External AI Services

| Service | Type | URL | Purpose |
|---|---|---|---|
| **Ollama** | Local LLM server | `http://ollama:11434` | Text generation + vision analysis |
| **Whisper Service** | Local STT | `http://whisper-service:8001` | Speech-to-text transcription |

Both are local-only, no external API dependencies (per ADR-002).

---

## 7. AI Infrastructure (Docker)

| Service | Image | Profile | Resources | Purpose |
|---|---|---|---|---|
| `ollama` | `ollama/ollama:0.6.0` | `ai` | 4 GB RAM | Local LLM hosting |
| `whisper-service` | Custom build | `ai` | 2 GB RAM | Speech-to-text |
| `celery-worker-text` | Custom build | `ai` | 1 GB RAM | Text gen worker |
| `celery-worker-image` | Custom build | `ai` | 1 GB RAM | Vision worker |
| `celery-worker-audio` | Custom build | `ai` | 1 GB RAM | Audio worker |
| `pgvector` | `pgvector/pgvector:pg16` | (always running) | 1 GB RAM | Vector DB support (dormant) |

Network: `ai-internal` (bridge, internal)

---

## 8. AI-Specific Documentation Files

| File | Purpose |
|---|---|
| `docs/adr/002-ai-local-only-strategy.md` | ADR: AI local-only strategy |
| `docs/runbooks/ai-outage.md` | AI outage runbook |
| `ops/runbooks/ai-outage.md` | AI outage ops runbook |
| `ops/design/ai-abuse-monitoring.md` | AI abuse monitoring design |
| `ops/ollama-trust-boundary.md` | Ollama trust boundary |
| `src/backend/docs/SRI-001-ai-sanitization-contract.md` | AI sanitization contract |
| `src/backend/scripts/audit_ai_sanitization.py` | AI sanitization audit script |

---

## 9. Frontend AI Components

| File | Purpose | Status |
|---|---|---|
| `web-dashboard/components/ai-section.tsx` | AI section wrapper (deprecated, no-op) | Inactive |
| `web-dashboard/components/ai-badge.tsx` | AI badge (deprecated, returns null) | Inactive |
| `web-dashboard/components/ai-settings-panel.tsx` | AI settings panel (unused in v1) | Inactive |
| `web-dashboard/lib/ai-settings.tsx` | AI settings (locked manual mode) | Inactive |
| `web-dashboard/lib/ai-validation.ts` | AI validation library | Inactive |
| `web-dashboard/lib/product-rules.ts` | Product rules (`AI_FEATURES_ENABLED = false`) | **Active control** |
| `web-dashboard/components/future-feature.tsx` | "Coming Soon" placeholder for AI features | Active |
| `mobile-app/constants/product-rules.ts` | Mobile product rules (`AI_FEATURES_ENABLED = false`) | **Active control** |

---

## 10. Test Files (AI-Related)

| File | Purpose |
|---|---|
| `tests/test_circuit_breaker.py` | Circuit breaker tests |
| `tests/test_validator.py` | AI validator tests |
| `tests/test_ssrf_validator.py` | SSRF validator tests |
| `tests/test_sanitization.py` | Sanitization tests |
| `tests/security/test_input_sanitization.py` | Input sanitization security tests |
| `tests/security/test_audit_signing.py` | Audit signing tests |
| `tests/adversarial/test_prompt_injection.py` | Prompt injection tests |
| `tests/adversarial/test_bypass_attempts.py` | Bypass attempt tests |
| `web-dashboard/tests/ai-validation.test.ts` | AI validation frontend tests |
| `web-dashboard/tests/product-rules.test.ts` | Product rules tests |
