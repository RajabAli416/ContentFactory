#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${CHROME_DEBUG_PORT:-9222}"
PROFILE="${CHROME_USER_DATA_DIR:-$ROOT/data/chrome-profile}"
mkdir -p "$PROFILE"

detect_chrome() {
  if [[ -n "${CHROME_PATH:-}" && -x "${CHROME_PATH}" ]]; then
    echo "$CHROME_PATH"
    return
  fi
  local candidates=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/usr/bin/google-chrome"
    "/usr/bin/google-chrome-stable"
    "/usr/bin/chromium"
    "/usr/bin/chromium-browser"
    "/snap/bin/chromium"
  )
  for c in "${candidates[@]}"; do
    if [[ -x "$c" ]]; then
      echo "$c"
      return
    fi
  done
  return 1
}

CHROME="$(detect_chrome || true)"
if [[ -z "$CHROME" ]]; then
  echo "[ERROR] Chrome/Chromium not found. Set CHROME_PATH in .env"
  exit 1
fi

echo "Launching Chrome with remote debugging on port $PORT"
echo "Profile: $PROFILE"
echo "Log into Snapgen or Zsky in this window, then restart ContentFactory."

exec "$CHROME" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  about:blank
