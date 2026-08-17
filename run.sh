#!/usr/bin/env bash
# One-command launcher for IT Copilot (local, private).
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

echo ""
echo "IT Copilot → http://127.0.0.1:8000"
exec uvicorn backend.main:app --host 127.0.0.1 --port 8000
