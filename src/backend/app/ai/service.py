from abc import ABC, abstractmethod
from typing import Any

from app.ai.schemas import AIOutputSchema


class AIService(ABC):
    @abstractmethod
    async def transcribe_audio(self, audio_path: str) -> str: ...

    @abstractmethod
    async def analyze_images(self, image_urls: list[str]) -> str: ...

    @abstractmethod
    async def generate_structured_output(
        self,
        transcript: str,
        vision_analysis: str,
        job_metadata: dict[str, Any],
    ) -> AIOutputSchema: ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...
