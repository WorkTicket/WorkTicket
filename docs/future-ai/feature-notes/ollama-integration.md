# Feature Note: Ollama LLM Integration

## Component Information

- **Name:** Ollama LLM Service
- **Files:** 
  - `src/backend/app/ai/ollama_service.py`
  - `src/backend/app/ai/service.py` (abstract base)
  - `src/scripts/docker/ollama-entrypoint.sh`
- **Dependencies:** Ollama server (ollama:11434)
- **Env Vars:** `OLLAMA_BASE_URL`, `OLLAMA_TEXT_MODEL`, `OLLAMA_VISION_MODEL`, `OLLAMA_TIMEOUT`
- **Infrastructure:** Ollama container, model files volume

## Current Status

Provides text generation (llama3.1) and vision analysis (llama3.2-vision) via Ollama local server. Includes:
- Prompt construction with structured output formatting (XML field wrapping)
- Input sanitization and injection defense
- JSON output parsing with error recovery
- Timeout handling and retry logic

**Production Readiness:** Beta — tested with local models
**Known Issues:** Model quality varies with quantization level (q4_0 is smallest, q8_0 better quality)
**Technical Debt:** Prompt templates should be versioned and A/B tested

## Reactivation Plan

1. Start Ollama: `docker compose --profile ai up ollama -d`
2. Wait for model pull (2-5 min first time)
3. Verify: `curl http://localhost:11434/api/tags`
4. Check AI health endpoint: `curl http://localhost:8000/health`

## Architecture Notes

Ollama is run as a separate Docker service on the `ai-internal` network. Only the backend and AI Celery workers can access it. Models are persisted in a Docker volume. The entrypoint script auto-pulls configured models on first start.
