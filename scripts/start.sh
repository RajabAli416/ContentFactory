#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Virtual environment missing. Run ./scripts/setup.sh first."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

# shellcheck disable=SC1091
source .venv/bin/activate

export PYTHONPATH=backend
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Starting ContentFactory backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
uvicorn app.main:app --app-dir backend --host "$BACKEND_HOST" --port "$BACKEND_PORT" --loop asyncio &
BACKEND_PID=$!

echo "Starting ContentFactory frontend on http://127.0.0.1:5173 ..."
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONTEND_PID=$!

sleep 2
echo
echo "Backend:  http://${BACKEND_HOST}:${BACKEND_PORT}/docs"
echo "Frontend: http://127.0.0.1:5173"
echo "Press Ctrl+C to stop."

wait
