#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/ayurveda-clinic.service"

echo "Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential curl nginx ufw

echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

echo "Creating runtime directories..."
mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/backups" "$PROJECT_ROOT/data" "$PROJECT_ROOT/temp"

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "Created .env from .env.example"
fi

echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r "$PROJECT_ROOT/requirements.txt"

echo "Configuring systemd service..."
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Ayurveda Clinic Management System
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/python3 $PROJECT_ROOT/run_server.py
Restart=always
RestartSec=5
EnvironmentFile=$PROJECT_ROOT/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ayurveda-clinic
sudo systemctl restart ayurveda-clinic

echo "Configuring UFW..."
sudo ufw allow 8000/tcp
sudo ufw allow OpenSSH
sudo ufw --force enable

EXTERNAL_IP="$(curl -fsSL ifconfig.me || true)"
echo "Deployment complete."
if [[ -n "$EXTERNAL_IP" ]]; then
  echo "Access URL: http://$EXTERNAL_IP:8000"
else
  echo "Access URL: http://YOUR_VM_EXTERNAL_IP:8000"
fi
