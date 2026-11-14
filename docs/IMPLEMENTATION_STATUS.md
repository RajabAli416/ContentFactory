# Implementation status

ContentFactory runs a live Gemini + Snapgen/Zsky pipeline end-to-end.

For current architecture, see [`ARCHITECTURE.md`](ARCHITECTURE.md).  
For install steps, see [`SETUP.md`](SETUP.md).

## Done

- Project / job orchestration with resume and WebSocket progress
- Gemini content and TTS providers (API key required)
- Desi mode (Urdu TTS, Roman Urdu captions, PK/IN packaging)
- Snapgen (default) and Zsky browser visual providers
- FFmpeg normalize / timeline / mux with optional scene audio bed
- Karaoke ASS captions with optional Whisper word alignment
- Export UI + QA checks
- Windows + macOS/Linux setup scripts
- CI workflow (pytest with offline stubs + frontend build)

## Known gaps / good first issues

- Live Snapgen/Zsky selectors need occasional updates as those UIs change
- Multi-job concurrency
- Richer BGM / SFX mixing beyond scene-bed volume
- Packaged desktop builds (optional)
- More caption languages and Whisper model presets in the UI

## Dependency pins

- Backend: `backend/requirements.txt`
- Frontend: `frontend/package.json`
