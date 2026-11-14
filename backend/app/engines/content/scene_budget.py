"""Scene count budgeting for fixed-length visual clips (e.g. Muse ~10s)."""

from __future__ import annotations

import math
from typing import Sequence

from app.core.config import get_settings
from app.schemas.content import GeneratedScene


def visual_clip_duration_seconds() -> float:
    return float(get_settings().visual_clip_duration_seconds)


def planned_scene_count(target_duration_seconds: int | float) -> int:
    """How many visual clips to generate for a target video length.

    Muse (and similar) emit fixed-length clips, so a 40s short with 10s clips
    needs exactly 4 scenes — not one scene per narration sentence.
    """
    clip = visual_clip_duration_seconds()
    target = max(float(target_duration_seconds), clip)
    count = int(math.ceil(target / clip))
    return max(count, 1)


def normalize_scenes_to_budget(
    scenes: Sequence[GeneratedScene],
    *,
    target_duration_seconds: int | float,
) -> list[GeneratedScene]:
    """Enforce scene count and set each scene duration to one visual clip."""
    clip = visual_clip_duration_seconds()
    budget = planned_scene_count(target_duration_seconds)
    items = list(scenes)

    if len(items) > budget:
        # Keep first N-1 beats, merge leftover narration into the final scene
        head = items[: budget - 1]
        tail = items[budget - 1 :]
        merged_text = " ".join(s.narration_text.strip() for s in tail if s.narration_text.strip())
        merged_caption = " ".join(
            (s.caption_text or s.narration_text).strip()
            for s in tail
            if (s.caption_text or s.narration_text).strip()
        )
        last = tail[0].model_copy(
            update={
                "narration_text": merged_text or tail[0].narration_text,
                "caption_text": merged_caption or tail[0].caption_text or merged_text,
                "sequence": budget,
                "scene_id": f"scene_{budget:03d}",
                "estimated_duration_seconds": clip,
            }
        )
        items = [*head, last]
    elif len(items) < budget and items:
        # Pad by splitting isn't reliable; duplicate visual intent is worse.
        # Leave short — assembly will freeze-extend to narration length.
        pass

    normalized: list[GeneratedScene] = []
    for i, scene in enumerate(items[:budget], start=1):
        normalized.append(
            scene.model_copy(
                update={
                    "scene_id": f"scene_{i:03d}",
                    "sequence": i,
                    "estimated_duration_seconds": clip,
                }
            )
        )
    return normalized
