"""Provider abstraction interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.schemas.content import ContentGenerationRequest, ContentGenerationResult


class ContentProvider(ABC):
    @abstractmethod
    async def generate_content(self, request: ContentGenerationRequest) -> ContentGenerationResult:
        raise NotImplementedError


class TTSProvider(ABC):
    @abstractmethod
    async def generate_speech(
        self,
        text: str,
        output_dir: Path,
        *,
        voice: str = "Aoede",
        style: str | None = None,
    ) -> dict[str, Any]:
        """Return dict with wav_path, mp3_path, duration_seconds, provider, voice."""
        raise NotImplementedError


class VideoGenerationProvider(ABC):
    @abstractmethod
    async def generate_clip(
        self,
        prompt: str,
        output_path: Path,
        *,
        options: dict[str, Any] | None = None,
        on_progress: Any | None = None,
    ) -> Path:
        raise NotImplementedError

    @abstractmethod
    async def check_ready(self) -> dict[str, Any]:
        raise NotImplementedError


class VideoProcessor(ABC):
    @abstractmethod
    async def process_clip(self, input_path: Path, options: dict[str, Any]) -> Path:
        raise NotImplementedError


class CaptionProvider(ABC):
    @abstractmethod
    async def generate_captions(
        self,
        audio_path: Path,
        script: str,
        output_dir: Path,
        *,
        style: dict[str, Any] | None = None,
        duration_seconds: float | None = None,
        spoken_text: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError
