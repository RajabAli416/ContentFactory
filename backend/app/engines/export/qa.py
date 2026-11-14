"""Automated export quality assurance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engines.video.ffmpeg_runner import probe_media
from app.schemas.manifest import ProductionManifest


async def run_qa_checks(manifest: ProductionManifest, render_path: Path) -> dict[str, Any]:
    settings = get_settings()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    passed = True

    def add(name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        nonlocal passed
        checks.append({"name": name, "ok": ok, "detail": detail, "warning": warn})
        if not ok and not warn:
            passed = False
        if warn:
            warnings.append(detail or name)

    add("final_exists", render_path.exists(), str(render_path))
    if not render_path.exists():
        return {"passed": False, "checks": checks, "warnings": warnings}

    size = render_path.stat().st_size
    add("final_non_empty", size > 0, f"{size} bytes")

    try:
        info = await probe_media(render_path)
        add("ffprobe_readable", True)
    except Exception as exc:
        add("ffprobe_readable", False, str(exc))
        return {"passed": False, "checks": checks, "warnings": warnings, "probe": None}

    w, h = info.get("width"), info.get("height")
    add(
        "resolution",
        w == settings.default_width and h == settings.default_height,
        f"{w}x{h}",
    )
    if w and h:
        ratio = w / h
        expected = 9 / 16
        add("aspect_ratio", abs(ratio - expected) < 0.05, f"{ratio:.4f}")

    fps = info.get("fps") or 0
    add("frame_rate", abs(fps - settings.default_fps) < 1.5, f"{fps}")
    add("video_codec", (info.get("video_codec") or "") in {"h264", "libx264", "avc1"}, str(info.get("video_codec")))
    add("audio_stream", bool(info.get("has_audio")), str(info.get("audio_codec")))

    vdur = float(info.get("duration") or 0)
    ndur = float(manifest.narration.duration_seconds or 0)
    add("video_duration_reasonable", vdur >= 1.0, f"{vdur:.2f}s")
    if ndur:
        diff = abs(vdur - ndur)
        ok = diff <= max(1.5, ndur * 0.1)
        add("narration_video_duration_match", ok, f"video={vdur:.2f} narration={ndur:.2f}", warn=not ok)
        if vdur + 0.5 < ndur:
            add("narration_not_truncated", False, "Video shorter than narration")

    missing_scenes = [
        s.scene_id
        for s in manifest.scenes
        if s.generation_status != "completed" or not s.raw_asset_path
    ]
    add("no_missing_scenes", len(missing_scenes) == 0, ",".join(missing_scenes) or "ok")

    caps_ok = bool(manifest.captions.srt_path and Path(manifest.captions.srt_path).exists())
    add("captions_exist", caps_ok, str(manifest.captions.srt_path))

    if vdur < 3:
        warnings.append("Suspiciously short export")
        add("not_suspiciously_short", False, f"{vdur:.2f}s", warn=True)

    return {
        "passed": passed,
        "checks": checks,
        "warnings": warnings,
        "probe": {
            "duration": vdur,
            "width": w,
            "height": h,
            "fps": fps,
            "video_codec": info.get("video_codec"),
            "audio_codec": info.get("audio_codec"),
            "size": size,
        },
    }
