"""Brainrot-style word-by-word highlighted ASS captions + SRT fallback.

Presets match the brainrot project: classic (yellow), hormozi (green), outline.
Word timings are proportional to word length across the narration duration
(Gemini TTS does not return boundaries).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engines.base import CaptionProvider

WHITE = "&H00FFFFFF&"
YELLOW = "&H0000F0FF&"
GREEN = "&H0000FF55&"
BLACK = "&H00000000&"

PRESETS = {
    # highlight, base_size, outline, uppercase_latin
    # Size scales down automatically when max_words is higher.
    "classic": (YELLOW, 110, 9, True),
    "hormozi": (GREEN, 118, 10, True),
    "outline": (WHITE, 104, 9, False),
}


def _font_size_for_chunk(base_size: int, max_words: int) -> int:
    """Keep longer caption chunks readable on 9:16 without overflow."""
    if max_words <= 3:
        return base_size
    if max_words <= 5:
        return max(78, int(base_size * 0.86))
    if max_words <= 7:
        return max(70, int(base_size * 0.74))
    if max_words <= 10:
        return max(62, int(base_size * 0.64))
    return max(56, int(base_size * 0.56))

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")


@dataclass
class WordTiming:
    text: str
    start: float
    end: float


def detect_script(text: str) -> str:
    if _ARABIC.search(text):
        return "urdu"
    if _DEVANAGARI.search(text):
        return "devanagari"
    return "latin"


def _ts_ass(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _ts_srt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _letters(word: str) -> str:
    return re.sub(r"[^\w\u0600-\u06FF\u0750-\u077F]", "", word, flags=re.UNICODE)


def _word_weight(word: str) -> float:
    """Duration proxy from spoken length — longer tokens hold captions longer."""
    letters = _letters(word)
    if not letters:
        return 1.15
    # Stronger length signal so karaoke does not race ahead of Urdu TTS
    return 1.15 + min(len(letters), 14) * 0.18


def _sentence_weight(sentence: str) -> float:
    words = sentence.split()
    if not words:
        return 1.0
    return sum(_word_weight(w) for w in words)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟۔])\s+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split((text or "").strip()) if p.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def speech_regions(
    duration: float,
    silences: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """Active speech intervals. Captions advance only here; pauses hold the last word."""
    lead = min(0.10, duration * 0.012)
    if duration <= 0:
        return [(0.0, 0.1)]
    if not silences:
        return [(lead, duration)]

    regions: list[tuple[float, float]] = []
    cursor = lead
    for s0, s1 in sorted(silences):
        s0 = max(0.0, min(duration, s0))
        s1 = max(0.0, min(duration, s1))
        if s0 > cursor + 0.04:
            regions.append((cursor, s0))
        cursor = max(cursor, s1)
    if cursor < duration - 0.04:
        regions.append((cursor, duration))
    regions = [(a, b) for a, b in regions if b - a >= 0.06]
    return regions or [(lead, duration)]


def _map_speech_time(
    regions: list[tuple[float, float]],
    speech_t: float,
) -> float:
    """Map a time on the concatenated speech timeline → wall-clock timestamp."""
    if not regions:
        return max(0.0, speech_t)
    lengths = [max(0.0, b - a) for a, b in regions]
    total = sum(lengths) or 1.0
    t = max(0.0, min(total, speech_t))
    acc = 0.0
    for (a, b), length in zip(regions, lengths):
        if acc + length >= t - 1e-9:
            return a + (t - acc)
        acc += length
    return regions[-1][1]


def _speech_span(regions: list[tuple[float, float]]) -> float:
    return sum(max(0.0, b - a) for a, b in regions) or 0.1


def _hold_through_pauses(words: list[WordTiming], duration: float) -> list[WordTiming]:
    """Make timings contiguous so karaoke freezes on the last word during audio pauses."""
    if not words:
        return words
    out: list[WordTiming] = []
    for i, w in enumerate(words):
        if i + 1 < len(words):
            end = max(w.end, words[i + 1].start)
        else:
            end = max(w.end, duration)
        out.append(WordTiming(text=w.text, start=w.start, end=end))
    return out


def _spread_words_on_speech(
    words: list[str],
    regions: list[tuple[float, float]],
    speech_start: float,
    speech_end: float,
    *,
    weight_words: list[str] | None = None,
) -> list[WordTiming]:
    """Place words on the speech-only timeline, then convert to wall clock."""
    if not words:
        return []
    span = max(0.05, speech_end - speech_start)
    source = weight_words if weight_words and len(weight_words) == len(words) else words
    weights = [_word_weight(w) for w in source]
    total = sum(weights) or 1.0
    out: list[WordTiming] = []
    cursor = speech_start
    for w, wt in zip(words, weights):
        dur = span * (wt / total)
        wall_start = _map_speech_time(regions, cursor)
        wall_end = _map_speech_time(regions, cursor + dur)
        if wall_end <= wall_start:
            wall_end = wall_start + 0.04
        out.append(WordTiming(text=w, start=wall_start, end=wall_end))
        cursor += dur
    return out


def align_caption_words(
    script: str,
    duration: float,
    *,
    spoken_text: str | None = None,
    silences: list[tuple[float, float]] | None = None,
) -> list[WordTiming]:
    """Align captions to narration with auto-pause on audio silence.

    Words only advance during detected speech. During pauses the previous
    word stays highlighted (hold-through). Sentence locks still apply when
    spoken Urdu and Roman Urdu sentence counts match.
    """
    caption_words = script.split()
    if not caption_words:
        return []

    regions = speech_regions(duration, silences)
    speech_len = _speech_span(regions)
    spoken = (spoken_text or "").strip()

    out: list[WordTiming] = []
    if spoken:
        spoken_sents = split_sentences(spoken)
        caption_sents = split_sentences(script)
        if len(spoken_sents) == len(caption_sents) and len(spoken_sents) >= 2:
            weights = [_sentence_weight(s) for s in spoken_sents]
            total = sum(weights) or 1.0
            cursor = 0.0
            for spoken_sent, caption_sent, wt in zip(spoken_sents, caption_sents, weights):
                sent_dur = speech_len * (wt / total)
                sent_end = cursor + sent_dur
                cap_words = caption_sent.split()
                spo_words = spoken_sent.split()
                if cap_words and spo_words and len(cap_words) == len(spo_words):
                    out.extend(
                        _spread_words_on_speech(
                            cap_words,
                            regions,
                            cursor,
                            sent_end,
                            weight_words=spo_words,
                        )
                    )
                else:
                    out.extend(
                        _spread_words_on_speech(
                            cap_words or [caption_sent],
                            regions,
                            cursor,
                            sent_end,
                        )
                    )
                cursor = sent_end
            return _hold_through_pauses(out, duration)

        spoken_words = spoken.split()
        if len(spoken_words) == len(caption_words):
            out = _spread_words_on_speech(
                caption_words,
                regions,
                0.0,
                speech_len,
                weight_words=spoken_words,
            )
            return _hold_through_pauses(out, duration)

    out = _spread_words_on_speech(caption_words, regions, 0.0, speech_len)
    return _hold_through_pauses(out, duration)


async def probe_silences(audio_path: Path, *, noise_db: float = -32.0, min_dur: float = 0.22) -> list[tuple[float, float]]:
    """Detect silence intervals via ffmpeg silencedetect (caption auto-pause)."""
    from app.engines.video.ffmpeg_runner import run_ffmpeg

    args = [
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f",
        "null",
        "-",
    ]
    try:
        # silencedetect logs to stderr; process may still exit 0
        _code, _stdout, stderr = await run_ffmpeg(args, check=False)
    except Exception:
        return []
    starts: list[float] = []
    silences: list[tuple[float, float]] = []
    for line in stderr.splitlines():
        if "silence_start:" in line:
            try:
                starts.append(float(line.split("silence_start:")[1].strip().split()[0]))
            except ValueError:
                pass
        elif "silence_end:" in line and starts:
            try:
                end = float(line.split("silence_end:")[1].strip().split()[0])
                silences.append((starts.pop(0), end))
            except ValueError:
                starts.clear()
    return silences


def _chunks(words: list[WordTiming], max_words: int, gap_break: float = 2.5) -> list[list[WordTiming]]:
    """Group words for on-screen display.

    High gap_break so short audio pauses keep the same chunk (highlight holds).
    """
    chunks: list[list[WordTiming]] = []
    cur: list[WordTiming] = []
    for w in words:
        gap = (w.start - cur[-1].end) if cur else 0.0
        # Contiguous hold timings usually have gap≈0; only hard-break on long holes
        if cur and (len(cur) >= max_words or gap > gap_break):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?؟۔]$", w.text):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_brainrot_ass(
    words: list[WordTiming],
    *,
    preset: str = "classic",
    fonts: dict[str, str] | None = None,
    width: int = 1080,
    height: int = 1920,
    max_words: int = 3,
    total_duration: float | None = None,
) -> str:
    if preset not in PRESETS:
        preset = "classic"
    highlight, base_size, outline, upper = PRESETS[preset]
    size = _font_size_for_chunk(base_size, max_words)
    fonts = fonts or {}
    script = detect_script(" ".join(w.text for w in words))
    font = fonts.get(script) or fonts.get("latin", "Arial Black")
    # Wider side margins when showing more words so lines stay on-frame
    side = 48 if max_words <= 3 else 36

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{WHITE},{WHITE},{BLACK},{BLACK},-1,0,0,0,100,100,0,0,1,{outline},0,5,{side},{side},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for chunk in _chunks(words, max_words):
        for i, active in enumerate(chunk):
            start = active.start
            # Hold through pauses: stay on this word until the next word starts
            if i + 1 < len(chunk):
                end = chunk[i + 1].start
            else:
                end = active.end
            if total_duration is not None:
                end = min(end, total_duration)
            if end <= start:
                continue
            parts: list[str] = []
            for j, w in enumerate(chunk):
                txt = _escape(
                    w.text.upper() if upper and detect_script(w.text) == "latin" else w.text
                )
                if j == i:
                    parts.append(
                        f"{{\\c{highlight}\\fscx112\\fscy112}}{txt}{{\\c{WHITE}\\fscx100\\fscy100}}"
                    )
                else:
                    parts.append(txt)
            pop = "{\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            events.append(
                f"Dialogue: 0,{_ts_ass(start)},{_ts_ass(end)},Cap,,0,0,0,,{pop}{' '.join(parts)}"
            )
    return header + "\n".join(events) + "\n"


def build_srt_from_chunks(words: list[WordTiming], max_words: int = 3) -> str:
    lines: list[str] = []
    idx = 1
    for chunk in _chunks(words, max_words):
        start = chunk[0].start
        end = chunk[-1].end
        text = " ".join(w.text for w in chunk)
        lines.append(str(idx))
        lines.append(f"{_ts_srt(start)} --> {_ts_srt(end)}")
        lines.append(text)
        lines.append("")
        idx += 1
    return "\n".join(lines)


class DurationCaptionProvider(CaptionProvider):
    async def generate_captions(
        self,
        audio_path: Path,
        script: str,
        output_dir: Path,
        *,
        style: dict[str, Any] | None = None,
        duration_seconds: float | None = None,
        spoken_text: str | None = None,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        settings = get_settings()
        style = style or {}

        if duration_seconds is None or duration_seconds <= 0:
            from app.engines.video.ffmpeg_runner import probe_media

            info = await probe_media(audio_path)
            duration_seconds = float(info.get("duration") or 1.0)

        preset = str(style.get("preset") or settings.caption_preset or "classic")
        desi = bool(style.get("desi"))
        default_max = (
            settings.caption_desi_max_words if desi else settings.caption_max_words
        )
        max_words = int(style.get("max_words") or default_max or 5)
        max_words = max(3, min(max_words, 12))
        fonts = {
            "latin": style.get("font") or settings.caption_font_latin,
            "urdu": settings.caption_font_urdu,
            "devanagari": settings.caption_font_devanagari,
        }

        aligner = "estimate"
        words: list[WordTiming] = []

        use_whisper = bool(
            style.get("whisper_align", settings.caption_whisper_align)
        )
        if use_whisper:
            try:
                from app.engines.captions.whisper_align import (
                    align_captions_with_whisper,
                    whisper_available,
                )

                if whisper_available():
                    import asyncio

                    from app.engines.captions.language import resolve_whisper_language

                    lang = resolve_whisper_language(
                        content_mode="desi" if desi else style.get("content_mode"),
                        project_language=style.get("project_language"),
                        spoken_text=spoken_text or script,
                        configured=settings.caption_whisper_language,
                        override=style.get("whisper_language"),
                    )
                    lang_tag = lang or "auto"
                    cache = (
                        audio_path.with_suffix("").parent
                        / f"whisper_words_{lang_tag}.json"
                    )
                    timed = await asyncio.to_thread(
                        align_captions_with_whisper,
                        audio_path,
                        script,
                        spoken_text=spoken_text,
                        language=lang,
                        model_size=str(
                            style.get("whisper_model") or settings.caption_whisper_model
                        ),
                        cache_path=cache,
                    )
                    words = [
                        WordTiming(text=w.text, start=w.start, end=w.end) for w in timed
                    ]
                    if words:
                        words[-1].end = max(words[-1].end, duration_seconds)
                        aligner = "whisper"
            except Exception as exc:
                # Fall back to estimate — never fail the pipeline on aligner errors
                from app.core.logging import get_logger

                get_logger(__name__).warning("Whisper caption align failed: %s", exc)

        if not words:
            silences = await probe_silences(audio_path)
            words = align_caption_words(
                script,
                duration_seconds,
                spoken_text=spoken_text,
                silences=silences,
            )

        ass_body = build_brainrot_ass(
            words,
            preset=preset,
            fonts=fonts,
            width=settings.default_width,
            height=settings.default_height,
            max_words=max_words,
            total_duration=duration_seconds,
        )
        srt_body = build_srt_from_chunks(words, max_words=max_words)

        # Also copy into captions/ and renders naming used by export
        srt_path = output_dir / "final_video.srt"
        ass_path = output_dir / "final_video.ass"
        srt_path.write_text(srt_body, encoding="utf-8")
        ass_path.write_text(ass_body, encoding="utf-8")

        return {
            "srt_path": str(srt_path),
            "ass_path": str(ass_path),
            "cue_count": len(words),
            "duration_seconds": duration_seconds,
            "provider": "brainrot_word_highlight",
            "aligner": aligner,
            "preset": preset,
        }
