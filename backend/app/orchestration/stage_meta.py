"""Human-readable pipeline stage metadata for progress events and UI."""

from __future__ import annotations

STAGE_META: dict[str, dict[str, str]] = {
    "PROJECT_CREATED": {
        "label": "Project created",
        "detail": "Workspace and manifest initialized",
    },
    "CONTENT_GENERATION": {
        "label": "Write script",
        "detail": "Draft narration, scenes, and packaging with the content provider",
    },
    "SCENE_PLANNING": {
        "label": "Plan scenes",
        "detail": "Lock scene order and duration budget for fixed-length clips",
    },
    "PROMPT_GENERATION": {
        "label": "Build visual prompts",
        "detail": "Write per-scene image/video prompts for the visual generator",
    },
    "NARRATION_GENERATION": {
        "label": "Generate narration",
        "detail": "Synthesize off-screen voiceover and normalize loudness",
    },
    "VISUAL_GENERATION": {
        "label": "Generate visuals",
        "detail": "Create and download each scene clip (Snapgen / Zsky)",
    },
    "ASSET_VALIDATION": {
        "label": "Validate assets",
        "detail": "Confirm every scene file is a readable video",
    },
    "CLIP_PROCESSING": {
        "label": "Process clips",
        "detail": "Normalize resolution/fps and fit clips to narration timing",
    },
    "TIMELINE_ASSEMBLY": {
        "label": "Assemble timeline",
        "detail": "Concatenate scene clips into one vertical timeline",
    },
    "CAPTION_GENERATION": {
        "label": "Generate captions",
        "detail": "Build karaoke ASS/SRT (Whisper align when enabled)",
    },
    "FINAL_RENDER": {
        "label": "Final render",
        "detail": "Mux narration, captions, and optional scene audio bed",
    },
    "QUALITY_ASSURANCE": {
        "label": "Quality check",
        "detail": "Probe duration, streams, and export readiness",
    },
    "COMPLETED": {
        "label": "Completed",
        "detail": "Pipeline finished successfully",
    },
}


def stage_label(stage: str | None) -> str:
    if not stage:
        return "Pipeline"
    meta = STAGE_META.get(stage)
    return meta["label"] if meta else stage.replace("_", " ").title()


def stage_detail(stage: str | None) -> str:
    if not stage:
        return ""
    meta = STAGE_META.get(stage)
    return meta["detail"] if meta else ""
