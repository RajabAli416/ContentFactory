/** Human-readable pipeline stage metadata (mirrors backend stage_meta). */

export const STAGE_META: Record<string, { label: string; detail: string }> = {
  PROJECT_CREATED: {
    label: "Project created",
    detail: "Workspace and manifest initialized",
  },
  CONTENT_GENERATION: {
    label: "Write script",
    detail: "Draft narration, scenes, and packaging",
  },
  SCENE_PLANNING: {
    label: "Plan scenes",
    detail: "Lock scene order and duration budget",
  },
  PROMPT_GENERATION: {
    label: "Build visual prompts",
    detail: "Write per-scene prompts for the visual generator",
  },
  NARRATION_GENERATION: {
    label: "Generate narration",
    detail: "Synthesize voiceover and normalize loudness",
  },
  VISUAL_GENERATION: {
    label: "Generate visuals",
    detail: "Create and download each scene clip",
  },
  ASSET_VALIDATION: {
    label: "Validate assets",
    detail: "Confirm every scene file is a readable video",
  },
  CLIP_PROCESSING: {
    label: "Process clips",
    detail: "Normalize resolution/fps and fit to narration",
  },
  TIMELINE_ASSEMBLY: {
    label: "Assemble timeline",
    detail: "Concatenate scene clips into one vertical timeline",
  },
  CAPTION_GENERATION: {
    label: "Generate captions",
    detail: "Build karaoke ASS/SRT captions",
  },
  FINAL_RENDER: {
    label: "Final render",
    detail: "Mux narration, captions, and optional scene audio",
  },
  QUALITY_ASSURANCE: {
    label: "Quality check",
    detail: "Probe duration, streams, and export readiness",
  },
  COMPLETED: {
    label: "Completed",
    detail: "Pipeline finished successfully",
  },
};

export const RUNNABLE_STAGES = Object.keys(STAGE_META).filter(
  (s) => s !== "PROJECT_CREATED"
);

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return "Pipeline";
  return STAGE_META[stage]?.label ?? stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function stageDetail(stage: string | null | undefined): string {
  if (!stage) return "";
  return STAGE_META[stage]?.detail ?? "";
}

export function formatStageStatus(status: string): string {
  return status.replace(/_/g, " ").toLowerCase();
}
