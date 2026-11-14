from __future__ import annotations

from app.engines.base import ContentProvider
from app.engines.content.gemini_provider import GeminiContentProvider


def get_content_provider() -> ContentProvider:
    return GeminiContentProvider()
