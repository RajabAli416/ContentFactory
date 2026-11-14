"""Near-perfect caption timing via Whisper word timestamps on the narration audio.

Gemini TTS does not return boundaries. We transcribe the finished WAV with
faster-whisper (word timestamps) and map those times onto the on-screen
caption words (English, Roman Urdu, etc.).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_MODEL = None
_MODEL_NAME: str | None = None


@dataclass
class TimedWord:
    text: str
    start: float
    end: float


def _norm_token(word: str) -> str:
    w = word.strip().lower()
    w = re.sub(r"[^\w\u0600-\u06FF\u0750-\u077F]+", "", w, flags=re.UNICODE)
    return w


def _load_model(model_size: str = "small"):
    global _MODEL, _MODEL_NAME
    if _MODEL is not None and _MODEL_NAME == model_size:
        return _MODEL
    from faster_whisper import WhisperModel

    # CPU int8 is the portable default on Windows without CUDA setup
    logger.info("Loading faster-whisper model=%s (first run may download weights)", model_size)
    _MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
    _MODEL_NAME = model_size
    return _MODEL


def _load_audio_16k_mono(audio_path: Path):
    """Decode audio via FFmpeg to float32 mono 16kHz — avoids PyAV API mismatches."""
    import numpy as np
    import subprocess

    from app.core.config import get_settings

    settings = get_settings()
    cmd = [
        settings.ffmpeg_path,
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(
            f"FFmpeg audio decode failed: {proc.stderr.decode('utf-8', 'replace')[-500:]}"
        )
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def whisper_word_timings(
    audio_path: Path,
    *,
    language: str | None = None,
    model_size: str = "small",
    cache_path: Path | None = None,
) -> list[TimedWord]:
    """Return word-level timestamps from the narration audio.

    ``language`` should be a Whisper code like ``en`` / ``ur``, or None to auto-detect.
    """
    if cache_path and cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            words = [
                TimedWord(text=w["text"], start=float(w["start"]), end=float(w["end"]))
                for w in raw.get("words") or []
                if w.get("text")
            ]
            if words:
                return words
        except Exception:
            pass

    model = _load_model(model_size)
    audio = _load_audio_16k_mono(audio_path)
    segments, _info = model.transcribe(
        audio,
        language=language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 200},
        condition_on_previous_text=False,
    )
    words: list[TimedWord] = []
    for seg in segments:
        for w in seg.words or []:
            text = (w.word or "").strip()
            if not text:
                continue
            start = float(w.start or 0.0)
            end = float(w.end or start + 0.05)
            if end <= start:
                end = start + 0.05
            words.append(TimedWord(text=text, start=start, end=end))

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "language": language,
                    "model": model_size,
                    "words": [{"text": w.text, "start": w.start, "end": w.end} for w in words],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return words


def _transfer_times(
    source_words: list[str],
    timed: list[TimedWord],
) -> list[TimedWord]:
    """Align transcript tokens to Whisper tokens; return timed source words."""
    if not source_words or not timed:
        return []

    a = [_norm_token(w) for w in source_words]
    b = [_norm_token(w.text) for w in timed]
    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    # Default: interpolate onto whisper spine
    assigned: list[TimedWord | None] = [None] * len(source_words)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                assigned[i] = TimedWord(
                    text=source_words[i], start=timed[j].start, end=timed[j].end
                )
        elif tag in {"replace", "delete", "insert"}:
            # Spread source slice across timed slice (or neighbors)
            src_slice = source_words[i1:i2]
            if not src_slice:
                continue
            if j1 < j2:
                t0 = timed[j1].start
                t1 = timed[j2 - 1].end
            elif j1 > 0:
                t0 = timed[j1 - 1].end
                t1 = timed[j1 - 1].end + 0.05 * len(src_slice)
            elif j2 < len(timed):
                t0 = timed[j2].start
                t1 = timed[j2].start + 0.05 * len(src_slice)
            else:
                t0 = timed[0].start
                t1 = timed[-1].end
            span = max(0.05, t1 - t0)
            for k, w in enumerate(src_slice):
                s = t0 + span * (k / len(src_slice))
                e = t0 + span * ((k + 1) / len(src_slice))
                assigned[i1 + k] = TimedWord(text=w, start=s, end=e)

    # Fill any holes by neighbor interpolation
    for i, item in enumerate(assigned):
        if item is not None:
            continue
        prev = next((assigned[j] for j in range(i - 1, -1, -1) if assigned[j]), None)
        nxt = next((assigned[j] for j in range(i + 1, len(assigned)) if assigned[j]), None)
        if prev and nxt:
            assigned[i] = TimedWord(
                text=source_words[i], start=prev.end, end=max(prev.end + 0.05, nxt.start)
            )
        elif prev:
            assigned[i] = TimedWord(
                text=source_words[i], start=prev.end, end=prev.end + 0.08
            )
        elif nxt:
            assigned[i] = TimedWord(
                text=source_words[i], start=max(0.0, nxt.start - 0.08), end=nxt.start
            )
        else:
            assigned[i] = TimedWord(text=source_words[i], start=0.0, end=0.08)

    # Enforce monotonic non-overlap
    out: list[TimedWord] = []
    cursor = 0.0
    for w in assigned:
        assert w is not None
        start = max(w.start, cursor)
        end = max(w.end, start + 0.04)
        out.append(TimedWord(text=w.text, start=start, end=end))
        cursor = end
    return out


def _map_caption_onto_spoken_times(
    caption_words: list[str],
    spoken_timed: list[TimedWord],
) -> list[TimedWord]:
    """Map Roman caption words onto timed spoken words (usually near 1:1)."""
    if not caption_words or not spoken_timed:
        return []
    if len(caption_words) == len(spoken_timed):
        return [
            TimedWord(text=c, start=s.start, end=s.end)
            for c, s in zip(caption_words, spoken_timed)
        ]

    # Proportional remap across the spoken timed spine
    n_c = len(caption_words)
    n_s = len(spoken_timed)
    out: list[TimedWord] = []
    for i, cw in enumerate(caption_words):
        a = i * n_s / n_c
        b = (i + 1) * n_s / n_c
        i0 = min(int(a), n_s - 1)
        i1 = min(max(int(b), i0), n_s - 1)
        f0 = a - int(a)
        f1 = b - int(b)
        start = spoken_timed[i0].start + (spoken_timed[i0].end - spoken_timed[i0].start) * f0
        if i1 > i0 and b >= i1:
            end = spoken_timed[i1].start + (spoken_timed[i1].end - spoken_timed[i1].start) * f1
        else:
            end = spoken_timed[i0].start + (spoken_timed[i0].end - spoken_timed[i0].start) * max(f1, f0 + 0.2)
        if end <= start:
            end = start + 0.05
        out.append(TimedWord(text=cw, start=start, end=end))

    # Contiguous hold (pause-friendly)
    for i in range(len(out) - 1):
        out[i] = TimedWord(text=out[i].text, start=out[i].start, end=max(out[i].end, out[i + 1].start))
    return out


def align_captions_with_whisper(
    audio_path: Path,
    caption_text: str,
    *,
    spoken_text: str | None = None,
    language: str | None = None,
    model_size: str = "small",
    cache_path: Path | None = None,
) -> list[TimedWord]:
    """Produce caption word timings locked to real audio via Whisper."""
    caption_words = caption_text.split()
    if not caption_words:
        return []

    whisper_words = whisper_word_timings(
        audio_path,
        language=language,
        model_size=model_size,
        cache_path=cache_path,
    )
    if not whisper_words:
        raise RuntimeError("Whisper returned no word timestamps")

    spoken = (spoken_text or "").strip()
    if spoken:
        spoken_timed = _transfer_times(spoken.split(), whisper_words)
        return _map_caption_onto_spoken_times(caption_words, spoken_timed)

    # No spoken script — map caption directly onto whisper spine
    return _map_caption_onto_spoken_times(caption_words, whisper_words)


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False
