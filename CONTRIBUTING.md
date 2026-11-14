# Contributing to ContentFactory

Thanks for helping improve an open, local-first faceless video pipeline.

## Ground rules

- Keep the product **faceless**: off-screen narration only — no avatar/cast/lip-sync systems
- Prefer small, focused pull requests
- Do not commit secrets, `.env`, `data/projects/`, or Chrome profiles
- Keep CI offline stubs working so `pytest` does not need real Gemini/Snapgen calls

## Development setup

1. Fork and clone the repo
2. Copy `.env.example` → `.env`
3. Run setup:
   - Windows: `setup.bat`
   - macOS / Linux: `./scripts/setup.sh`
4. Start the app:
   - Windows: `startup.bat`
   - macOS / Linux: `./scripts/start.sh`
5. Run tests:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
export PYTHONPATH=backend   # Windows: set PYTHONPATH=backend
cd backend && pytest -q
```

## Project map

| Area | Path |
|------|------|
| API + orchestrator | `backend/app/` |
| Content / TTS / captions / video | `backend/app/engines/` |
| React UI | `frontend/src/` |
| Docs | `docs/` |

## Pull request checklist

- [ ] `pytest` still passes offline (stubs in `conftest.py`)
- [ ] New env vars added to `.env.example` with safe defaults
- [ ] User-facing behavior documented in `README.md` or `docs/`
- [ ] Tests added or updated when behavior changes
- [ ] No secrets or personal project assets included

## Feature ideas that fit well

- Additional visual providers behind the same interface
- Better caption languages / Whisper models
- Export presets per platform
- Hardening Snapgen/Zsky selectors with diagnostics

## Feature ideas that need discussion first

- Cloud multi-user hosting
- Talking-head / avatar pipelines (out of scope for the core product)
- Scraping or bypassing site auth/CAPTCHA
