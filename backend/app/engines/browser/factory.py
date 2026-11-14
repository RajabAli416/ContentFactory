from __future__ import annotations

from app.core.config import get_settings
from app.engines.base import VideoGenerationProvider
from app.engines.browser.snapgen_provider import SnapgenVideoGenerationProvider
from app.engines.browser.zsky_provider import ZskyVideoGenerationProvider


def get_video_generation_provider() -> VideoGenerationProvider:
    settings = get_settings()
    if settings.video_gen_provider == "zsky":
        return ZskyVideoGenerationProvider()
    return SnapgenVideoGenerationProvider()
