import logging
from typing import Any

import httpx

from app.ai.schemas import AIOutputSchema
from app.ai.service import AIService
from app.ai.ssrf_validator import validate_url
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhisperService(AIService):
    _client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if WhisperService._client is None:
            timeout = httpx.Timeout(300.0)
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            )
            WhisperService._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return WhisperService._client

    async def transcribe_audio(self, audio_path: str, trace_id: str | None = None) -> str:
        try:
            validate_url(audio_path, label="audio URL")
        except ValueError as e:
            logger.error("Audio URL validation failed: %s", e)
            return ""

        whisper_url = settings.whisper_service_url.rstrip("/")
        client = self._get_client()
        try:
            trace_id = trace_id or audio_path.split("/")[-1][:64] if "/" in audio_path else ""
            headers = {
                "X-Trace-Id": trace_id,
                "X-Request-ID": trace_id,
                "X-Correlation-ID": trace_id,
            }
            if settings.whisper_api_key:
                headers["Authorization"] = f"Bearer {settings.whisper_api_key}"
            resp = await client.post(
                f"{whisper_url}/transcribe/url",
                json={"url": audio_path},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("text", "")
        except httpx.TimeoutException:
            logger.error("Whisper service request timed out")
            return ""
        except httpx.HTTPStatusError as e:
            logger.error("Whisper service HTTP error: %s", e)
            return ""
        except Exception as e:
            logger.error("Whisper transcription request failed: %s", e)
            return ""

    async def analyze_images(self, image_urls: list[str]) -> str:
        logger.warning("WhisperService does not support image analysis. Use OllamaService.")
        return ""

    async def generate_structured_output(
        self,
        transcript: str,
        vision_analysis: str,
        job_metadata: dict[str, Any],
    ) -> AIOutputSchema:
        logger.warning("WhisperService does not support text generation. Use OllamaService.")
        return AIOutputSchema()

    async def health(self) -> dict[str, Any]:
        whisper_url = settings.whisper_service_url.rstrip("/")
        client = self._get_client()
        try:
            resp = await client.get(f"{whisper_url}/health")
            resp.raise_for_status()
            data = resp.json()
            return {
                "available": data.get("status") == "ok",
                "model_size": data.get("model_size", "unknown"),
                "device": data.get("device", "cpu"),
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "model_size": settings.whisper_model_size,
                "device": "cpu",
            }
