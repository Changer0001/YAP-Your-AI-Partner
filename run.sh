#!/usr/bin/env bash
# One-command launcher for YAP (local, private).
# Bind address/port come from .env (HOST/PORT). Default is localhost only.
# To reach YAP from other devices on your LAN, set HOST=0.0.0.0 in .env.
set -e
cd "$(dirname "$0")"

# 1. Python environment
if [ ! -d "venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 2. Config
[ -f .env ] || cp .env.example .env

# 3. Check Ollama + models (informational only)
if command -v ollama >/dev/null 2>&1; then
  ollama list | grep -q "qwen2.5:3b"      || echo "NOTE: run 'ollama pull qwen2.5:3b'"
  ollama list | grep -q "nomic-embed-text" || echo "NOTE: run 'ollama pull nomic-embed-text'"
else
  echo "NOTE: Ollama not found. Install from https://ollama.com and pull the models."
fi

# Read HOST/PORT from .env (falls back to localhost:8000)
HOST="$(grep -E '^HOST=' .env 2>/dev/null | tail -1 | cut -d= -f2)"
PORT="$(grep -E '^PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo ""
if [ "$HOST" = "0.0.0.0" ]; then
  LANIP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "YAP → http://${LANIP:-<this-machine-ip>}:${PORT}  (reachable on your LAN)"
else
  echo "YAP → http://${HOST}:${PORT}"
fi
exec uvicorn backend.main:app --host "$HOST" --port "$PORT"
