"""Structured content generation schemas for Gemini/mock providers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContentGenerationRequest(BaseModel):
    topic: str
    target_duration_seconds: int = 45
    platform: str = "youtube_shorts"
    tone: str = "informative"
    visual_aesthetic: str = "cinematic documentary"
    language: str = "English"
    content_mode: Literal["standard", "desi"] = "standard"
    extra_instructions: str | None = None
    narration_voice: str = "Aoede"


class GeneratedScene(BaseModel):
    scene_id: str
    sequence: int
    narration_text: str
    caption_text: str = ""
    visual_description: str
    video_prompt: str
    negative_prompt: str = (
        "text overlays, subtitles, watermarks, talking head, presenter, avatar"
    )
    estimated_duration_seconds: float = 5.0
    visual_style: str = "cinematic documentary"
    camera_movement: str = "slow dolly forward"
    composition: str = "vertical 9:16"
    transition_suggestion: str = "hard_cut"


class ContentPackaging(BaseModel):
    post_title: str = ""
    post_caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    hashtag_string: str = ""
    markets: list[str] = Field(default_factory=list)
    caption_script: str = "latin"
    spoken_script: str = "latin"


class ContentGenerationResult(BaseModel):
    title: str
    hook: str
    full_script: str
    caption_text: str = ""
    closing_line: str
    estimated_duration_seconds: float
    scenes: list[GeneratedScene] = Field(default_factory=list)
    packaging: ContentPackaging | None = None
    research_notes: str | None = None
    factual_disclaimer: str | None = (
        "Content may include speculative framing; verify facts before publishing."
    )
    extras: dict[str, Any] = Field(default_factory=dict)


class SceneUpdate(BaseModel):
    narration_text: str | None = None
    visual_description: str | None = None
    video_prompt: str | None = None
    negative_prompt: str | None = None
    estimated_duration_seconds: float | None = None
    visual_style: str | None = None
    camera_movement: str | None = None
    composition: str | None = None
