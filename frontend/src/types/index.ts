export interface Project {
  id: string;
  title: string;
  topic: string;
  status: string;
  platform: string;
  language: string;
  content_mode: string;
  tone: string;
  visual_aesthetic: string;
  narration_voice: string;
  target_duration_seconds: number;
  aspect_ratio: string;
  extra_instructions: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  topic: string;
  title?: string;
  target_duration_seconds?: number;
  platform?: string;
  language?: string;
  content_mode?: string;
  tone?: string;
  visual_aesthetic?: string;
  narration_voice?: string;
  aspect_ratio?: string;
  extra_instructions?: string;
}

export interface ManifestScene {
  scene_id: string;
  sequence: number;
  narration_text: string;
  caption_text?: string;
  visual_description: string;
  video_prompt: string;
  negative_prompt: string;
  estimated_duration_seconds: number;
  visual_style: string;
  camera_movement: string;
  composition: string;
  generation_status: string;
  raw_asset_path: string | null;
  processed_asset_path: string | null;
  actual_duration_seconds: number | null;
}

export interface ProductionManifest {
  schema_version: string;
  project_id: string;
  title: string;
  topic: string;
  status: string;
  created_at: string;
  updated_at: string;
  settings: Record<string, unknown> & { content_mode?: string };
  script: {
    title: string;
    hook: string;
    full_text: string;
    caption_text?: string;
    closing_line: string;
    estimated_duration_seconds: number | null;
  };
  packaging?: {
    post_title: string;
    post_caption: string;
    hashtags: string[];
    hashtag_string: string;
    markets: string[];
    caption_script: string;
    spoken_script: string;
  };
  narration: {
    provider: string;
    voice: string;
    audio_path: string | null;
    wav_path: string | null;
    mp3_path: string | null;
    duration_seconds: number | null;
    status: string;
  };
  scenes: ManifestScene[];
  captions: {
    srt_path: string | null;
    ass_path: string | null;
    status: string;
  };
  render: {
    output_path: string | null;
    status: string;
    duration_seconds: number | null;
    qa_status: string;
    qa_report: Record<string, unknown> | null;
  };
  pipeline_stages: Array<{
    stage: string;
    status: string;
    error: string | null;
  }>;
}

export interface JobStage {
  stage: string;
  sequence: number;
  status: string;
  retry_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Job {
  id: string;
  project_id: string;
  job_type: string;
  status: string;
  current_stage: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  stages: JobStage[];
}

export interface JobEvent {
  job_id: string;
  project_id?: string;
  status: string;
  stage?: string;
  stage_label?: string;
  stage_detail?: string;
  stage_index?: number | null;
  stage_total?: number | null;
  scene_id?: string;
  scene_index?: number;
  scene_total?: number;
  scene_count?: number;
  message?: string;
  progress_pct?: number | null;
  step?: string;
  duration_seconds?: number;
  level?: string;
  timestamp?: string;
}

export interface SystemHealth {
  status: string;
  version: string;
  ffmpeg: string;
  ffprobe: string;
  chrome_cdp: boolean;
  gemini_configured?: boolean;
  video_gen_provider?: string;
}
