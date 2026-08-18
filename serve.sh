#!/usr/bin/env bash
# Runtime launcher used by the YAP systemd service (no dependency install).
# Bind address/port come from .env (HOST/PORT); defaults to localhost:8000.
set -e
cd "$(dirname "$0")"
HOST="$(grep -E '^HOST=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' "')"
PORT="$(grep -E '^PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' "')"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
exec ./venv/bin/uvicorn backend.main:app --host "$HOST" --port "$PORT"
