"""FFmpeg/FFprobe subprocess helpers — never load whole media into memory.

Uses a thread + subprocess.run so Windows event loops that lack
subprocess transport support (common with uvicorn --reload) still work.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    pass


def _run_cmd(cmd: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"Command timed out after {timeout}s: {cmd[0]}") from exc
    except FileNotFoundError as exc:
        raise FFmpegError(f"Executable not found: {cmd[0]}") from exc
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    return completed.returncode, stdout, stderr


async def run_ffmpeg(
    args: list[str],
    *,
    timeout: float = 600.0,
    check: bool = True,
) -> tuple[int, str, str]:
    settings = get_settings()
    cmd = [settings.ffmpeg_path, *args]
    logger.debug("ffmpeg: %s", " ".join(cmd))
    code, stdout, stderr = await asyncio.to_thread(_run_cmd, cmd, timeout)
    if check and code != 0:
        raise FFmpegError(f"FFmpeg failed ({code}): {stderr[-2000:]}")
    return code, stdout, stderr


async def run_ffprobe(args: list[str], *, timeout: float = 60.0) -> tuple[int, str, str]:
    settings = get_settings()
    cmd = [settings.ffprobe_path, *args]
    return await asyncio.to_thread(_run_cmd, cmd, timeout)


def _parse_probe_output(stdout: str) -> dict[str, Any]:
    data = json.loads(stdout or "{}")
    format_info = data.get("format") or {}
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None
    )
    fps = None
    if video_stream and video_stream.get("r_frame_rate"):
        num, _, den = video_stream["r_frame_rate"].partition("/")
        try:
            fps = float(num) / float(den or 1)
        except ValueError:
            fps = None
    return {
        "duration": float(format_info.get("duration") or 0),
        "size": int(format_info.get("size") or 0),
        "format_name": format_info.get("format_name"),
        "width": int(video_stream["width"]) if video_stream and video_stream.get("width") else None,
        "height": int(video_stream["height"]) if video_stream and video_stream.get("height") else None,
        "fps": fps,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "has_video": video_stream is not None,
        "has_audio": audio_stream is not None,
        "raw": data,
    }


def probe_media_sync(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    settings = get_settings()
    code, stdout, stderr = _run_cmd(
        [
            settings.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=60.0,
    )
    if code != 0:
        raise FFmpegError(f"FFprobe failed for {path}: {stderr[-1000:]}")
    return _parse_probe_output(stdout)


def validate_video_file_sync(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing video: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Empty video file: {path}")
    info = probe_media_sync(path)
    if not info.get("has_video"):
        raise ValueError(f"No video stream: {path}")
    if not info.get("duration") or info["duration"] <= 0:
        raise ValueError(f"Invalid duration: {path}")
    return info


async def probe_media(path: Path) -> dict[str, Any]:
    return await asyncio.to_thread(probe_media_sync, path)


async def validate_video_file(path: Path) -> dict[str, Any]:
    return await asyncio.to_thread(validate_video_file_sync, path)
