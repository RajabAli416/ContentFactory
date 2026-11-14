"""Centralized AI model identifiers and provider configuration.

Do not scatter model names throughout the codebase — import from here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class AIConfig:
    text_model: str
    tts_model: str
    api_key: str
    speaking_rate_wpm: int

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def require_api_key(self) -> str:
        if not self.has_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required. Set it in your .env file "
                "(copy from .env.example)."
            )
        return self.api_key


def get_ai_config() -> AIConfig:
    s = get_settings()
    return AIConfig(
        text_model=s.gemini_text_model,
        tts_model=s.gemini_tts_model,
        api_key=s.gemini_api_key,
        speaking_rate_wpm=s.speaking_rate_wpm,
    )
