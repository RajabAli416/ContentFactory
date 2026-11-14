# Setup guide

## Prerequisites

Install these before running ContentFactory:

| Tool | Notes |
|------|--------|
| Python 3.11+ | `python --version` |
| Node.js 18+ | `node --version` |
| FFmpeg + FFprobe | Must be on `PATH` |
| Google Chrome | Required for Snapgen/Zsky visuals |
| Gemini API key | Required — set `GEMINI_API_KEY` in `.env` |

### FFmpeg tips

- Windows: [ffmpeg.org](https://ffmpeg.org/download.html) or `winget install FFmpeg`
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`

## Install

### Windows

```bat
setup.bat
```

### macOS / Linux

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

This creates `.venv`, installs Python + Node deps, Playwright Chromium (for automation), and copies `.env.example` → `.env` if missing.

## Run

### Windows

```bat
startup.bat
```

### macOS / Linux

```bash
./scripts/start.sh
```

Open http://127.0.0.1:5173

## First-run checklist

1. Set `GEMINI_API_KEY` in `.env`
2. Set `VIDEO_GEN_PROVIDER=snapgen` (or `zsky`)
3. Set `CHROME_PATH` for your OS in `.env` if the default is wrong
4. Start CDP Chrome:
   - Windows: `scripts\launch_chrome_cdp.bat`
   - macOS/Linux: `./scripts/launch_chrome_cdp.sh`
5. Sign in manually in that browser window
6. Restart the ContentFactory backend
7. Create a project and run the pipeline

## Desi mode

In **New project**, select Content mode → **Desi**.

Optional `.env` tweaks:

```env
CAPTION_WHISPER_ALIGN=true
CAPTION_WHISPER_MODEL=small
CAPTION_WHISPER_LANGUAGE=auto
CAPTION_DESI_MAX_WORDS=10
SCENE_AUDIO_VOLUME=0.22
```

`CAPTION_WHISPER_LANGUAGE=auto` uses **en** for standard/English projects and **ur** for Desi/Urdu. Force `en` or `ur` if needed.

First Whisper run downloads a model (needs disk + network once).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ffmpeg` / `ffprobe` missing | Install FFmpeg and reopen the terminal |
| Backend starts but UI cannot connect | Confirm ports `8000` / `5173` and `CORS_ORIGINS` |
| Live visuals fail immediately | Chrome CDP not running, or not logged in — check `data/projects/*/logs/browser/` |
| Gemini / TTS errors | Check `GEMINI_API_KEY`, model names in `.env`, and backend logs |
| Windows Playwright/FFmpeg weirdness | Do not use `uvicorn --reload`; use `startup.bat` |
| Whisper align fails | Pipeline falls back to estimated captions; check logs and `faster-whisper` install |

## Updating

```bash
git pull
source .venv/bin/activate   # or Windows activate
pip install -r backend/requirements.txt
cd frontend && npm install
```
