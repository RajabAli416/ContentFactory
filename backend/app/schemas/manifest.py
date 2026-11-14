"""Versioned production manifest schemas — source of truth for the pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


MANIFEST_SCHEMA_VERSION = "1.0.0"

StageStatus = Literal[
    "pending", "running", "completed", "failed", "paused", "cancelled", "skipped"
]
GenerationStatus = Literal[
    "pending", "queued", "generating", "downloading", "completed", "failed", "paused"
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManifestSettings(BaseModel):
    target_duration_seconds: int = 45
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    fps: int = 30
    language: str = "English"
    content_mode: Literal["standard", "desi"] = "standard"
    platform: str = "youtube_shorts"
    tone: str = "informative"
    visual_aesthetic: str = "cinematic documentary"
    narration_voice: str = "Aoede"
    extra_instructions: str | None = None
    transition: str = "hard_cut"
    transition_duration: float = 0.3
    gap_fill_strategy: str = "freeze_frame"
    end_trim_seconds: float = 0.0


class ManifestScript(BaseModel):
    title: str = ""
    hook: str = ""
    full_text: str = ""
    caption_text: str = ""
    closing_line: str = ""
    estimated_duration_seconds: float | None = None


class ManifestPackaging(BaseModel):
    post_title: str = ""
    post_caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    hashtag_string: str = ""
    markets: list[str] = Field(default_factory=list)
    caption_script: str = "latin"
    spoken_script: str = "latin"


class ManifestNarration(BaseModel):
    provider: str = ""
    voice: str = "Aoede"
    audio_path: str | None = None
    wav_path: str | None = None
    mp3_path: str | None = None
    duration_seconds: float | None = None
    status: StageStatus = "pending"
    metadata_path: str | None = None
    style: str | None = None


class ManifestScene(BaseModel):
    scene_id: str
    sequence: int
    narration_text: str = ""
    caption_text: str = ""
    visual_description: str = ""
    video_prompt: str = ""
    negative_prompt: str = (
        "text overlays, subtitles, watermarks, talking head, presenter, "
        "avatar, lip sync, logo, UI elements"
    )
    estimated_duration_seconds: float = 5.0
    visual_style: str = "cinematic documentary"
    camera_movement: str = "slow dolly forward"
    composition: str = "vertical 9:16"
    generation_status: GenerationStatus = "pending"
    raw_asset_path: str | None = None
    processed_asset_path: str | None = None
    actual_duration_seconds: float | None = None
    start_time_seconds: float | None = None
    end_time_seconds: float | None = None


class ManifestCaptions(BaseModel):
    srt_path: str | None = None
    ass_path: str | None = None
    status: StageStatus = "pending"
    style: dict[str, Any] = Field(
        default_factory=lambda: {
            "preset": "classic",
            "font": "Arial Black",
            "font_size": 96,
            "text_color": "#FFFFFF",
            "highlight_color": "#F5C542",
            "outline": True,
            "max_words": 10,
            "max_lines": 1,
            "vertical_position": 0.5,
        }
    )



class ManifestRender(BaseModel):
    output_path: str | None = None
    status: StageStatus = "pending"
    duration_seconds: float | None = None
    qa_status: StageStatus = "pending"
    qa_report: dict[str, Any] | None = None
    metadata_path: str | None = None


class ManifestPipelineStage(BaseModel):
    stage: str
    status: StageStatus = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    retry_count: int = 0


class ProductionManifest(BaseModel):
    schema_version: str = MANIFEST_SCHEMA_VERSION
    project_id: str
    title: str
    topic: str
    status: str = "draft"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    settings: ManifestSettings = Field(default_factory=ManifestSettings)
    script: ManifestScript = Field(default_factory=ManifestScript)
    packaging: ManifestPackaging = Field(default_factory=ManifestPackaging)
    narration: ManifestNarration = Field(default_factory=ManifestNarration)
    scenes: list[ManifestScene] = Field(default_factory=list)
    captions: ManifestCaptions = Field(default_factory=ManifestCaptions)
    render: ManifestRender = Field(default_factory=ManifestRender)
    pipeline_stages: list[ManifestPipelineStage] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()


PIPELINE_STAGES = [
    "PROJECT_CREATED",
    "CONTENT_GENERATION",
    "SCENE_PLANNING",
    "PROMPT_GENERATION",
    "NARRATION_GENERATION",
    "VISUAL_GENERATION",
    "ASSET_VALIDATION",
    "CLIP_PROCESSING",
    "TIMELINE_ASSEMBLY",
    "CAPTION_GENERATION",
    "FINAL_RENDER",
    "QUALITY_ASSURANCE",
    "COMPLETED",
]


def default_pipeline_stages() -> list[ManifestPipelineStage]:
    return [ManifestPipelineStage(stage=s) for s in PIPELINE_STAGES]


def create_initial_manifest(
    project_id: str,
    title: str,
    topic: str,
    *,
    target_duration_seconds: int = 45,
    platform: str = "youtube_shorts",
    language: str = "English",
    content_mode: Literal["standard", "desi"] = "standard",
    tone: str = "informative",
    visual_aesthetic: str = "cinematic documentary",
    narration_voice: str = "Aoede",
    extra_instructions: str | None = None,
    aspect_ratio: str = "9:16",
) -> ProductionManifest:
    if content_mode == "desi":
        language = language if language and language.lower() not in {"english", "en"} else "Urdu"
        platform = platform or "tiktok"
        tone = tone if tone and tone != "informative" else "conversational desi storytelling"
    settings = ManifestSettings(
        target_duration_seconds=target_duration_seconds,
        platform=platform,
        language=language,
        content_mode=content_mode,
        tone=tone,
        visual_aesthetic=visual_aesthetic,
        narration_voice=narration_voice,
        extra_instructions=extra_instructions,
        aspect_ratio=aspect_ratio,
    )
    stages = default_pipeline_stages()
    stages[0].status = "completed"
    stages[0].completed_at = utc_now_iso()
    return ProductionManifest(
        project_id=project_id,
        title=title,
        topic=topic,
        status="draft",
        settings=settings,
        narration=ManifestNarration(voice=narration_voice),
        pipeline_stages=stages,
    )
