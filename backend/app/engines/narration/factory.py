from __future__ import annotations

from app.engines.base import TTSProvider
from app.engines.narration.gemini_provider import GeminiTTSProvider


def get_tts_provider() -> TTSProvider:
    return GeminiTTSProvider()
