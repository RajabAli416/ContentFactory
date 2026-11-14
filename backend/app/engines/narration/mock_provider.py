"""Mock TTS — generates a real WAV/MP3 tone timed to estimated speech length."""

from __future__ import annotations

import json
import math
import re
import struct
import wave
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engines.base import TTSProvider
from app.engines.video.ffmpeg_runner import run_ffmpeg


def _word_count(text: str) -> int:
    return max(len(re.findall(r"\w+", text)), 1)


def _write_tone_wav(path: Path, duration_seconds: float, sample_rate: int = 48000) -> None:
    """Write a quiet sine tone so the file is a valid narration stand-in."""
    duration_seconds = max(duration_seconds, 1.0)
    n_samples = int(sample_rate * duration_seconds)
    freq = 220.0
    amplitude = 0.08
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            # Soft envelope to avoid clicks
            t = i / sample_rate
            env = min(1.0, t * 4, max(0.0, (duration_seconds - t) * 4))
            sample = int(amplitude * env * 32767 * math.sin(2 * math.pi * freq * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)


class MockTTSProvider(TTSProvider):
    async def generate_speech(
        self,
        text: str,
        output_dir: Path,
        *,
        voice: str = "Aoede",
        style: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        output_dir.mkdir(parents=True, exist_ok=True)
        words = _word_count(text)
        duration = (words / max(settings.speaking_rate_wpm, 1)) * 60.0
        duration = max(duration, 2.0)

        wav_path = output_dir / "master.wav"
        mp3_path = output_dir / "master.mp3"
        meta_path = output_dir / "narration_metadata.json"

        _write_tone_wav(wav_path, duration)
        await run_ffmpeg(
            [
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-ar",
                "48000",
                "-b:a",
                "192k",
                str(mp3_path),
            ]
        )

        meta = {
            "provider": "mock",
            "voice": voice,
            "style": style,
            "text_length": len(text),
            "word_count": words,
            "duration_seconds": duration,
            "wav_path": str(wav_path),
            "mp3_path": str(mp3_path),
            "note": "Mock TTS tone — not real speech. Marked as mock output.",
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {
            "provider": "mock",
            "voice": voice,
            "wav_path": str(wav_path),
            "mp3_path": str(mp3_path),
            "duration_seconds": duration,
            "metadata_path": str(meta_path),
        }
