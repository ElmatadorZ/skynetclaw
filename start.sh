#!/usr/bin/env bash
# SkynetClaw — start the backend on Linux / macOS.
#
#   ./start.sh              # start on 127.0.0.1:8766
#   ./start.sh 9000         # start on a different port
#   PORT=9000 ./start.sh    # same, via environment
#
# The Windows equivalent is start.bat.
set -euo pipefail

cd "$(dirname "$0")"

PORT="${1:-${PORT:-8766}}"
HOST="${HOST:-127.0.0.1}"

# ── virtualenv ────────────────────────────────────────────────────────────────
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "No .venv found. Creating one..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r backend/requirements.txt
  echo "  dependencies installed"
fi

# ── configuration ─────────────────────────────────────────────────────────────
if [ ! -f backend/settings.json ]; then
  cp backend/settings.example.json backend/settings.json
  echo "  created backend/settings.json from the template — edit it to choose your model"
fi
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "  created .env from the template"
fi

# ── database ──────────────────────────────────────────────────────────────────
( cd backend && python migrate.py up >/dev/null 2>&1 ) || {
  echo "  migration failed — run 'cd backend && python migrate.py up' to see why" >&2
  exit 1
}

# ── model runtime (advisory only; SkynetClaw also works with a cloud API) ─────
if command -v ollama >/dev/null 2>&1; then
  if ! curl -sf --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "  note: ollama is installed but not responding on :11434 — run 'ollama serve'"
  fi
else
  echo "  note: ollama not found. Use a cloud provider via .env, or install from https://ollama.com"
fi

echo
echo "SkynetClaw starting on http://${HOST}:${PORT}"
echo "  health    : http://${HOST}:${PORT}/api/system/health"
echo "  dashboard : http://${HOST}:${PORT}/api/council/dashboard"
echo "  chamber   : open 'THE CONTINENTAL DIVISION.html' in a browser"
echo

cd backend
exec python -m uvicorn main:app --host "$HOST" --port "$PORT"
