"""Gemini TTS via the Interactions API (same path as the brainrot project).

generate_content + speechConfig fails on gemini-*-tts models; Interactions
accepts speech_config.voice and returns audio bytes (WAV or PCM).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

from app.core.ai_config import get_ai_config
from app.core.logging import get_logger
from app.engines.base import TTSProvider
from app.engines.video.ffmpeg_runner import probe_media, run_ffmpeg

logger = get_logger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class GeminiTTSProvider(TTSProvider):
    async def generate_speech(
        self,
        text: str,
        output_dir: Path,
        *,
        voice: str = "Aoede",
        style: str | None = None,
    ) -> dict[str, Any]:
        cfg = get_ai_config()
        api_key = cfg.require_api_key()

        output_dir.mkdir(parents=True, exist_ok=True)
        delivery = style or "conversational, natural pace, clear short-form narration"

        try:
            audio = await asyncio.to_thread(
                self._synthesize_bytes,
                api_key,
                cfg.tts_model,
                text,
                voice,
                delivery,
            )
        except Exception as exc:
            logger.error("Gemini TTS failed: %s", exc)
            raise RuntimeError(f"Gemini TTS failed: {exc}") from exc

        wav_path = output_dir / "master.wav"
        mp3_path = output_dir / "master.mp3"
        meta_path = output_dir / "narration_metadata.json"

        if audio.startswith(b"RIFF"):
            wav_path.write_bytes(audio)
        else:
            self._pcm_to_wav(audio, wav_path, sample_rate=24000)

        normalized = output_dir / "master_normalized.wav"
        await run_ffmpeg(
            [
                "-y",
                "-i",
                str(wav_path),
                "-ar",
                "48000",
                "-ac",
                "1",
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                str(normalized),
            ]
        )
        if normalized.exists():
            wav_path.write_bytes(normalized.read_bytes())
            normalized.unlink(missing_ok=True)

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

        probe = await probe_media(wav_path)
        duration = float(probe.get("duration") or 0)
        meta = {
            "provider": "gemini",
            "voice": voice,
            "style": delivery,
            "model": cfg.tts_model,
            "api": "interactions",
            "duration_seconds": duration,
            "wav_path": str(wav_path),
            "mp3_path": str(mp3_path),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {
            "provider": "gemini",
            "voice": voice,
            "wav_path": str(wav_path),
            "mp3_path": str(mp3_path),
            "duration_seconds": duration,
            "metadata_path": str(meta_path),
        }

    def _synthesize_bytes(
        self,
        api_key: str,
        model: str,
        text: str,
        voice: str,
        style: str,
        max_retries: int = 4,
    ) -> bytes:
        last_err = "unknown error"
        for attempt in range(max_retries):
            try:
                data = self._call(api_key, model, text, voice, style)
                audio = self._audio_bytes(data)
                if audio:
                    return audio
                last_err = "response contained no audio"
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                last_err = f"HTTP {e.code}: {detail}"
                if e.code in (400, 401, 403, 404):
                    raise RuntimeError(f"Gemini TTS failed: {last_err}") from e
                time.sleep(2**attempt)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(2**attempt)
        raise RuntimeError(f"Gemini TTS failed after {max_retries} tries: {last_err}")

    def _call(self, api_key: str, model: str, text: str, voice: str, style: str) -> dict:
        body = {
            "model": model,
            "input": [
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [{"type": "speech_metadata", "style": style}],
                        }
                    ],
                }
            ],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]},
        }
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _audio_bytes(data: dict) -> bytes | None:
        found: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "audio" and isinstance(node.get("data"), str):
                    found.append(node["data"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
        if not found:
            return None
        return base64.b64decode(found[-1])

    def _pcm_to_wav(self, pcm: bytes, path: Path, sample_rate: int = 24000) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        path.write_bytes(buf.getvalue())
