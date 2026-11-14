import pytest
from pathlib import Path

from app.engines.captions.provider import DurationCaptionProvider, WordTiming, _chunks
from app.engines.narration.mock_provider import MockTTSProvider


def test_word_chunks():
    words = [
        WordTiming(text=w, start=i * 0.3, end=i * 0.3 + 0.25)
        for i, w in enumerate("One two three four five six seven eight nine".split())
    ]
    chunks = _chunks(words, max_words=4)
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_caption_files(tmp_path: Path):
    tts = MockTTSProvider()
    audio_meta = await tts.generate_speech("Hello world from the desert after rain.", tmp_path / "nar")
    caps = DurationCaptionProvider()
    result = await caps.generate_captions(
        Path(audio_meta["wav_path"]),
        "Hello world from the desert after rain. The bloom is brief and bright.",
        tmp_path / "caps",
        duration_seconds=audio_meta["duration_seconds"],
    )
    srt = Path(result["srt_path"])
    ass = Path(result["ass_path"])
    assert srt.exists() and "-->" in srt.read_text(encoding="utf-8")
    assert ass.exists() and "[Events]" in ass.read_text(encoding="utf-8")
