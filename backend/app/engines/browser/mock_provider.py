"""Mock video generation — produces real vertical MP4 clips via FFmpeg."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.core.config import get_settings
from app.engines.base import VideoGenerationProvider
from app.engines.video.ffmpeg_runner import run_ffmpeg, validate_video_file

ProgressCb = Callable[[str], Awaitable[None]] | Callable[[str], None] | None


class MockVideoGenerationProvider(VideoGenerationProvider):
    async def check_ready(self) -> dict[str, Any]:
        return {
            "ready": True,
            "provider": "mock",
            "message": "Mock video provider is always ready.",
        }

    async def generate_clip(
        self,
        prompt: str,
        output_path: Path,
        *,
        options: dict[str, Any] | None = None,
        on_progress: ProgressCb = None,
    ) -> Path:
        settings = get_settings()
        opts = options or {}
        duration = float(opts.get("duration_seconds") or 5.0)
        width = int(opts.get("width") or settings.default_width)
        height = int(opts.get("height") or settings.default_height)
        fps = int(opts.get("fps") or settings.default_fps)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if on_progress:
            result = on_progress("Generating mock clip with FFmpeg testsrc")
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]

        # Deterministic color from prompt hash
        digest = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        color = f"0x{digest[:6]}"
        label = (prompt[:40] or "mock").replace(":", " ").replace("'", "")

        await run_ffmpeg(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={width}x{height}:d={duration:.3f}:r={fps}",
                "-vf",
                (
                    f"drawtext=text='MOCK {label}':fontsize=36:fontcolor=white:"
                    f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.4"
                ),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-t",
                f"{duration:.3f}",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        # If drawtext font missing, retry without text
        try:
            await validate_video_file(output_path)
        except Exception:
            await run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc=size={width}x{height}:rate={fps}:duration={duration:.3f}",
                    "-vf",
                    "format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )
            await validate_video_file(output_path)

        if on_progress:
            result = on_progress(f"Mock clip saved: {output_path.name}")
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]
        return output_path
