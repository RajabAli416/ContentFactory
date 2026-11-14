"""Dedicated Chrome CDP instance helpers."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def is_chrome_debugging_alive(port: int | None = None) -> bool:
    settings = get_settings()
    port = port or settings.chrome_debug_port
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return "webSocketDebuggerUrl" in data or "Browser" in data
    except Exception:
        return False


def video_gen_start_url() -> str:
    settings = get_settings()
    if settings.video_gen_provider == "zsky":
        return settings.zsky_base_url
    return settings.snapgen_base_url


async def ensure_chrome_cdp() -> dict[str, Any]:
    settings = get_settings()
    if is_chrome_debugging_alive():
        return {"running": True, "port": settings.chrome_debug_port, "launched": False}

    chrome = Path(settings.chrome_path)
    if not chrome.exists():
        return {
            "running": False,
            "port": settings.chrome_debug_port,
            "launched": False,
            "error": f"Chrome not found at {settings.chrome_path}",
        }

    user_data = Path(settings.chrome_user_data_dir)
    user_data.mkdir(parents=True, exist_ok=True)
    start_url = video_gen_start_url()
    args = [
        str(chrome),
        f"--remote-debugging-port={settings.chrome_debug_port}",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check",
        start_url,
    ]
    logger.info(
        "Launching dedicated Chrome CDP on port %s (%s)",
        settings.chrome_debug_port,
        settings.video_gen_provider,
    )
    # Detached process via subprocess (Windows-safe; avoids asyncio subprocess gaps)
    subprocess.Popen(  # noqa: S603
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    for _ in range(20):
        await asyncio.sleep(0.5)
        if is_chrome_debugging_alive():
            return {"running": True, "port": settings.chrome_debug_port, "launched": True}
    return {
        "running": False,
        "port": settings.chrome_debug_port,
        "launched": True,
        "error": "Chrome launched but CDP not reachable",
    }
