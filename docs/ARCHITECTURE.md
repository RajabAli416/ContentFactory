# Architecture

ContentFactory is a **local-first** production system: a FastAPI backend orchestrates providers and FFmpeg; a React UI drives projects and monitors jobs.

## Stack

| Layer | Choice |
|-------|--------|
| UI | React 19 + TypeScript + Vite + Tailwind |
| API | FastAPI + WebSockets |
| DB | SQLite + SQLAlchemy + Alembic |
| AI text/TTS | Gemini (`google-genai` / Interactions TTS) |
| Visuals | Snapgen Muse or Zsky via Playwright CDP |
| Captions | ASS karaoke (+ optional faster-whisper align) |
| Encode | FFmpeg |

## Pipeline stages

```text
PROJECT_CREATED
CONTENT_GENERATION
SCENE_PLANNING
PROMPT_GENERATION
NARRATION_GENERATION
VISUAL_GENERATION
ASSET_VALIDATION
CLIP_PROCESSING
TIMELINE_ASSEMBLY
CAPTION_GENERATION
FINAL_RENDER
QUALITY_ASSURANCE
COMPLETED
```

Jobs are single-flight (one active production job). Stages are resumable via the versioned project `manifest.json` plus SQLite.

## Provider interfaces

All engines sit behind small abstractions in `backend/app/engines/base.py`:

- `ContentProvider` — script + scenes (+ packaging)
- `TTSProvider` — narration WAV/MP3
- `VideoGenerationProvider` — one clip per scene prompt
- `VideoProcessor` — normalize / assemble / mux
- `CaptionProvider` — SRT/ASS

Factories always return live providers (Gemini + Snapgen/Zsky). Offline stubs exist only under `backend/tests` for CI.

## Data layout (per project)

```text
data/projects/{project_id}/
  manifest.json
  scripts/
  narration/
  prompts/
  assets/downloaded|processed/
  captions/
  renders/final_video.mp4
  logs/
```

Original downloads are kept; processing writes new files.

## Creative constraint

Faceless only: narration is off-screen voiceover. Visual prompts forbid presenters, avatars, baked-in subtitles, and watermarks where possible.

## Modes

- **Standard** — general short-form scripting
- **Desi** — Urdu speech + Roman Urdu captions + PK/IN TikTok packaging helpers

## Known limitations

- Snapgen/Zsky UIs change; selectors may need updates — failures save diagnostics under `logs/browser/`
- One active job at a time
- Live browser automation requires a human-authenticated Chrome profile
- Whisper alignment is optional and CPU-heavy on first model download
- Not a multi-tenant cloud SaaS — harden carefully if you expose the API beyond localhost
