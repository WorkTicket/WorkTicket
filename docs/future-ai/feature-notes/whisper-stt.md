# Feature Note: Whisper Speech-to-Text

## Component Information

- **Name:** Whisper Speech-to-Text Service
- **Files:** 
  - `src/backend/app/ai/whisper_service.py` (client)
  - `src/whisper-service/app.py` (standalone service)
  - `src/whisper-service/Dockerfile`
- **Dependencies:** Whisper service (whisper-service:8001)
- **Env Vars:** `WHISPER_SERVICE_URL`, `WHISPER_MODEL_SIZE`, `WHISPER_API_KEY`
- **Infrastructure:** Whisper service container, model files

## Current Status

Provides audio transcription using faster-whisper (local STT). Audio files are sent to the whisper microservice which returns text transcripts. Used for voice-to-job workflows where technicians describe jobs verbally.

**Production Readiness:** Beta — functional but not extensively tested in field
**Known Issues:** Large audio files may exceed timeout; model size trades speed for accuracy
**Technical Debt:** Audio format validation should be improved

## Reactivation Plan

1. Start Whisper: `docker compose --profile ai up whisper-service -d`
2. Verify: `curl http://localhost:8001/health`
3. Test with sample audio file via AI process endpoint

## Architecture Notes

Whisper runs as a separate microservice on the `ai-internal` network. This separation allows independent scaling and resource allocation. The base model is used by default (fastest, lowest memory). Larger models (small, medium, large-v3) are available via `WHISPER_MODEL_SIZE` env var.
