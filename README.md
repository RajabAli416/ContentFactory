# ContentFactory

**Open-source, local-first factory for faceless short-form video.**

Give it a topic. It writes a script, narrates it, generates vertical clips, burns karaoke captions, and exports a ready-to-post **1080×1920** MP4 — for YouTube Shorts, TikTok, and Instagram Reels.

No avatars. No talking heads. No cloud lock-in. Your keys and media stay on your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)

---

## What it does

```text
Topic
  → Script + scene plan          (Gemini)
  → Narration audio              (Gemini TTS)
  → Visual clips                 (Snapgen / Zsky)
  → Timeline + karaoke captions  (FFmpeg + Whisper align)
  → Final MP4 + TikTok packaging
```

| Mode | Narration | Captions | Best for |
|------|-----------|----------|----------|
| **Standard** | English (or your language) | Matching on-screen text | Global Shorts / Reels |
| **Desi** | Urdu TTS | Roman Urdu karaoke + PK/IN hashtags | Pakistan / India TikTok |

## Features

- Full production pipeline with resume / retry and live job progress
- Gemini content + TTS (API key required)
- Browser automation for **Snapgen Muse** (default) or **Zsky**
- Brainrot-style word-highlight captions (`classic` / `hormozi` / `outline`)
- Optional **Whisper** word-level caption sync for near-perfect karaoke
- Scene ambient audio ducked under narration
- Export panel with caption + hashtag packaging (especially useful in Desi mode)

## Requirements

- **Python** 3.11+
- **Node.js** 18+
- **FFmpeg** + **FFprobe** on your `PATH`
- **Google Chrome** (for Snapgen/Zsky)
- A **Gemini API key** (required)

Works on **Windows**, **macOS**, and **Linux**.

## Quick start

### 1. Clone

```bash
git clone https://github.com/RajabAli416/ContentFactory.git
cd ContentFactory
```

### 2. Configure

```bash
cp .env.example .env
# Set GEMINI_API_KEY=... in .env
```

### 3. Install & run

**Windows**

```bat
setup.bat
startup.bat
```

**macOS / Linux**

```bash
chmod +x scripts/setup.sh scripts/start.sh scripts/launch_chrome_cdp.sh
./scripts/setup.sh
./scripts/start.sh
```

Then open:

- App UI → http://127.0.0.1:5173  
- API docs → http://127.0.0.1:8000/docs  

### 4. Connect visuals

1. In `.env`: `VIDEO_GEN_PROVIDER=snapgen` (or `zsky`)
2. Launch a dedicated Chrome debug profile:
   - Windows: `scripts\launch_chrome_cdp.bat`
   - macOS / Linux: `./scripts/launch_chrome_cdp.sh`
3. Log into Snapgen (or Zsky) manually in that Chrome window  
4. Restart the backend and run a project from the UI  

ContentFactory never bypasses login or CAPTCHA.

## Desi mode

When creating a project, choose **Desi**:

- Spoken script → Urdu (for TTS)
- On-screen captions → Roman Urdu
- Export → TikTok caption + Pakistan/India-oriented hashtags

Whisper caption alignment auto-picks the ASR language (Urdu for Desi, English for standard). Override with `CAPTION_WHISPER_LANGUAGE=en` / `ur` / `auto`.

## Configuration

All settings live in `.env` (see `.env.example`). Important knobs:

| Variable | Meaning |
|----------|---------|
| `GEMINI_API_KEY` | Google AI Studio / Gemini key (**required**) |
| `VIDEO_GEN_PROVIDER` | `snapgen` or `zsky` |
| `CAPTION_PRESET` | `classic` / `hormozi` / `outline` |
| `CAPTION_WHISPER_ALIGN` | `true` for audio-locked karaoke |
| `CAPTION_WHISPER_LANGUAGE` | `auto` (English→`en`, Desi→`ur`), or force `en` / `ur` |
| `SCENE_AUDIO_VOLUME` | Ambient clip bed under narration (e.g. `0.22`) |

Never commit `.env`.

## Project layout

```text
ContentFactory/
├── backend/          FastAPI app, pipeline, providers
├── frontend/         React + Vite workspace UI
├── docs/             Architecture & deeper guides
├── scripts/          Setup / start / Chrome CDP helpers
├── data/             Local runtime (gitignored projects & DB)
├── setup.bat         Windows installer
├── startup.bat       Windows launcher
└── .env.example      Safe defaults for new installs
```

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/SETUP.md`](docs/SETUP.md)

## Development

```bash
# Backend
source .venv/bin/activate          # Windows: .venv\Scripts\activate
export PYTHONPATH=backend          # Windows: set PYTHONPATH=backend
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm run dev

# Tests
cd backend && pytest -q
```

On Windows, avoid `uvicorn --reload` for live browser/FFmpeg runs (selector loop issues). `startup.bat` already starts without reload.

## Tests

```bash
cd backend
pytest -q
```

CI uses offline stub providers so tests do not call Gemini or Snapgen.

## Third-party services

ContentFactory orchestrates tools you bring:

- **Google Gemini** — script + TTS (your API key, their terms)
- **Snapgen / Zsky** — visual generation via your browser login (their terms)
- **FFmpeg** — local encoding
- **faster-whisper** — optional local caption alignment (model download on first use)

This project does not sell access to those services and does not bypass their authentication.

## Contributing

PRs welcome! See [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Good first contributions: provider adapters, caption languages, UI polish, docs translations, CI, and selector hardening with diagnostics.

## Security

Report vulnerabilities privately — see [`SECURITY.md`](SECURITY.md).

## License

[MIT](LICENSE) © ContentFactory contributors

---

Built for creators who want a **repeatable faceless pipeline** they can own, audit, and extend.
