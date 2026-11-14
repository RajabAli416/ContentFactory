"""System health and config endpoints."""

from __future__ import annotations

import shutil

from fastapi import APIRouter

from app import __version__
from app.core.ai_config import get_ai_config
from app.core.config import get_settings
from app.engines.browser.chrome import is_chrome_debugging_alive

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    ffmpeg_ok = shutil.which(settings.ffmpeg_path) is not None or settings.ffmpeg_path.endswith(
        ("ffmpeg", "ffmpeg.exe")
    )
    # which may fail for bare 'ffmpeg' if PATH has it — try running later; for health just check PATH
    ffmpeg_path = shutil.which(settings.ffmpeg_path) or settings.ffmpeg_path
    ffprobe_path = shutil.which(settings.ffprobe_path) or settings.ffprobe_path
    return {
        "status": "ok",
        "version": __version__,
        "ffmpeg": ffmpeg_path,
        "ffprobe": ffprobe_path,
        "chrome_cdp": is_chrome_debugging_alive(),
        "database": settings.database_url,
        "gemini_configured": bool(settings.gemini_api_key),
        "video_gen_provider": settings.video_gen_provider,
    }


@router.get("/config")
async def config() -> dict:
    settings = get_settings()
    ai = get_ai_config()
    return {
        "gemini_text_model": ai.text_model,
        "gemini_tts_model": ai.tts_model,
        "gemini_configured": ai.has_api_key,
        "backend_host": settings.backend_host,
        "backend_port": settings.backend_port,
        "default_resolution": f"{settings.default_width}x{settings.default_height}",
        "default_fps": settings.default_fps,
        "video_gen_provider": settings.video_gen_provider,
        "snapgen_base_url": settings.snapgen_base_url,
        "zsky_base_url": settings.zsky_base_url,
        "chrome_debug_port": settings.chrome_debug_port,
        "speaking_rate_wpm": settings.speaking_rate_wpm,
        # Never expose API keys
    }
