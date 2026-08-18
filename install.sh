#!/usr/bin/env bash
# One-time installer: sets YAP up as an always-on service (starts on boot, auto-restarts),
# and — if Tailscale is present — publishes it over HTTPS so phones don't see "not secure".
#
# Run from the project folder:   ./install.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"
cd "$DIR"

echo "==> Installing YAP from: $DIR   (user: $USER_NAME)"

# 1. Python environment + dependencies
if [ ! -d venv ]; then
  echo "==> Creating virtual environment"
  python3 -m venv venv
fi
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
chmod +x serve.sh run.sh 2>/dev/null || true

# 2. Free port 8000 (stop any old service / manual run)
echo "==> Stopping any previous instance"
sudo systemctl disable --now it-copilot 2>/dev/null || true   # old service name, if present
sudo systemctl stop yap 2>/dev/null || true
pkill -f "uvicorn backend.main:app" 2>/dev/null || true
sleep 1

# 3. Create the systemd service
echo "==> Creating systemd service (yap.service)"
sudo tee /etc/systemd/system/yap.service >/dev/null <<EOF
[Unit]
Description=YAP - local IT knowledge assistant
After=network-online.target ollama.service
Wants=network-online.target ollama.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/serve.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now yap
sleep 2
echo "==> Service status:"
systemctl is-active yap && echo "    yap is running." || {
  echo "    yap failed to start — showing recent logs:"; journalctl -u yap -n 15 --no-pager; exit 1; }

# 4. HTTPS via Tailscale (removes the 'not secure' warning on phones)
if command -v tailscale >/dev/null 2>&1; then
  PORT="$(grep -E '^PORT=' .env | tail -1 | cut -d= -f2- | tr -d ' "')"; PORT="${PORT:-8000}"
  echo "==> Publishing over HTTPS via Tailscale Serve (port $PORT)"
  if sudo tailscale serve --bg "$PORT" 2>/dev/null; then
    echo "==> Your secure URL:"
    tailscale serve status || true
  else
    echo "    Could not enable Tailscale Serve automatically."
    echo "    Enable HTTPS once in the Tailscale admin console (DNS -> MagicDNS + HTTPS Certificates),"
    echo "    then run:  sudo tailscale serve --bg $PORT"
  fi
else
  echo "==> Tailscale not found — skipping HTTPS setup."
fi

echo ""
echo "==> Done. YAP now starts automatically on boot."
echo "    Manage:  sudo systemctl {status|restart|stop} yap"
echo "    Logs:    journalctl -u yap -f"
echo "    Update:  git pull && sudo systemctl restart yap"
