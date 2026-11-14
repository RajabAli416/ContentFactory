import pytest

from app.engines.content.scene_budget import (
    normalize_scenes_to_budget,
    planned_scene_count,
)
from app.engines.content.mock_provider import MockContentProvider
from app.schemas.content import ContentGenerationRequest, GeneratedScene


def test_planned_scene_count_for_40s(tmp_data):
    assert planned_scene_count(40) == 4
    assert planned_scene_count(45) == 5
    assert planned_scene_count(10) == 1
    assert planned_scene_count(11) == 2


def test_normalize_merges_extra_scenes(tmp_data):
    scenes = [
        GeneratedScene(
            scene_id=f"scene_{i:03d}",
            sequence=i,
            narration_text=f"Beat {i}",
            visual_description="v",
            video_prompt="p",
            estimated_duration_seconds=5,
        )
        for i in range(1, 7)
    ]
    out = normalize_scenes_to_budget(scenes, target_duration_seconds=40)
    assert len(out) == 4
    assert out[-1].narration_text.startswith("Beat 4")
    assert "Beat 5" in out[-1].narration_text
    assert "Beat 6" in out[-1].narration_text
    assert all(s.estimated_duration_seconds == 10.0 for s in out)


@pytest.mark.asyncio
async def test_mock_provider_respects_budget(tmp_data):
    result = await MockContentProvider().generate_content(
        ContentGenerationRequest(topic="Desert bloom", target_duration_seconds=40)
    )
    assert len(result.scenes) == 4
    assert all(s.estimated_duration_seconds == 10.0 for s in result.scenes)
