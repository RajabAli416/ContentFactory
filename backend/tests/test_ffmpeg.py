from pathlib import Path

import pytest

from app.engines.browser.mock_provider import MockVideoGenerationProvider
from app.engines.video.ffmpeg_runner import probe_media, validate_video_file
from app.engines.video.processor import FFmpegVideoProcessor


@pytest.mark.asyncio
async def test_normalize_and_concat(tmp_path: Path):
    provider = MockVideoGenerationProvider()
    clips = []
    for i in range(2):
        out = tmp_path / f"clip_{i}.mp4"
        await provider.generate_clip(
            f"test prompt {i}",
            out,
            options={"duration_seconds": 1.5, "width": 1080, "height": 1920, "fps": 30},
        )
        await validate_video_file(out)
        clips.append(out)

    processor = FFmpegVideoProcessor()
    normed = []
    for i, clip in enumerate(clips):
        n = tmp_path / f"norm_{i}.mp4"
        await processor.normalize_clip(clip, n)
        info = await probe_media(n)
        assert info["width"] == 1080
        assert info["height"] == 1920
        normed.append(n)

    concat = tmp_path / "out.mp4"
    await processor.concatenate(normed, concat, transition="hard_cut")
    info = await probe_media(concat)
    assert info["has_video"]
    assert info["duration"] > 2.0
