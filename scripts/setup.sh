#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "============================================"
echo " ContentFactory Setup"
echo "============================================"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] '$1' not found on PATH."
    exit 1
  fi
}

need python3
need node
need npm

if command -v ffmpeg >/dev/null 2>&1; then
  echo "[OK] ffmpeg found"
else
  echo "[WARN] ffmpeg not found on PATH"
fi
if command -v ffprobe >/dev/null 2>&1; then
  echo "[OK] ffprobe found"
else
  echo "[WARN] ffprobe not found on PATH"
fi

if [[ ! -d .venv ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "Installing Playwright Chromium (optional for live Snapgen/Zsky)..."
playwright install chromium >/dev/null 2>&1 || true

echo "Installing frontend dependencies..."
(cd frontend && npm install)

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — set GEMINI_API_KEY before running."
fi

mkdir -p data/projects data/assets data/exports data/logs data/database data/chrome-profile

echo
echo "Setup complete."
echo "Next: ./scripts/start.sh"
echo "For visuals: ./scripts/launch_chrome_cdp.sh then log into Snapgen/Zsky"
