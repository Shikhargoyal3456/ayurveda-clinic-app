#!/usr/bin/env bash
set -Eeuo pipefail

# Dr. Kash AI GCP Compute Engine deployment script
#
# Usage on the VM:
#   1. Copy this file to the VM as deploy.sh
#   2. Run: chmod +x deploy.sh
#   3. Run: ./deploy.sh
#
# This script is idempotent:
# - It safely installs missing packages
# - Clones the repo if absent, otherwise pulls the latest main branch
# - Rewrites the .env, systemd service, and Nginx config in place
# - Restarts services only after validation

PROJECT_ID="essential-topic-433910-r5"
VM_NAME="kash-ai-prod"
ZONE="asia-south1-b"
EXTERNAL_IP="35.244.0.89"
REPO_URL="https://github.com/Shikhargoyal3456/ayurveda-clinic-app.git"
APP_DIR="/opt/kash-ai"
APP_USER="${SUDO_USER:-$USER}"
APP_GROUP="$(id -gn "$APP_USER")"
APP_SERVICE="kash-ai"
APP_PORT="8000"
APP_HOST="127.0.0.1"
PYTHON_BIN="python3"
VENV_DIR="${APP_DIR}/.venv"
ENV_FILE="${APP_DIR}/.env"
SYSTEMD_FILE="/etc/systemd/system/${APP_SERVICE}.service"
NGINX_SITE="/etc/nginx/sites-available/${APP_SERVICE}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${APP_SERVICE}"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

retry() {
  local attempts="$1"
  shift
  local count=1
  until "$@"; do
    if (( count >= attempts )); then
      return 1
    fi
    sleep $((count * 2))
    count=$((count + 1))
  done
}

write_env_file() {
  log "Writing production .env"
  sudo mkdir -p "$(dirname "$ENV_FILE")"
  sudo tee "$ENV_FILE" >/dev/null <<'EOF'
ENVIRONMENT=production
DEBUG=false
APP_NAME=kash-ai
CLINIC_NAME=Kash ai
APP_VERSION=1.0.0
SECRET_KEY=c2f2f7f32cd3f888ff835293df0baed85f4e8b07d051d9fc6bce2f25e2234333

HOST=0.0.0.0
PORT=8000
RELOAD=false
UVICORN_RELOAD=false

DATABASE_URL=sqlite:///./ayurveda.db?cache=shared&timeout=30
SQLITE_WAL_MODE=true
SQLITE_TIMEOUT=30

SESSION_TIMEOUT=28800
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=900
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_SPECIAL=true
SESSION_HTTPS_ONLY=true
CSRF_ENABLED=false
ADMIN_USERNAMES=admin@ayurveda.com,shikhar_temp_admin

RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://35.244.0.89
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://35.244.0.89
CORS_ALLOW_CREDENTIALS=true
TRUSTED_HOSTS=localhost,127.0.0.1,35.244.0.89

OLLAMA_API_URL=http://localhost:11434
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_HOST=http://localhost:11434
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
AI_TIMEOUT=30
STARTUP_RAG_WARMUP=false
STARTUP_LLM_WARMUP=false
AI_ENABLED=true
AI_RETRY_COUNT=3
USE_AI_FALLBACK=true
AI_CACHE_SIZE=100
AI_CACHE_TTL_HOURS=24

LOG_LEVEL=info
LOG_FILE=logs/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=7
BACKUP_PATH=backups

GOOGLE_SPEECH_API_KEY=AIzaSyBDXExi8nTK0QiljQ3_0JQVP6jPcdCBTdM
VERTEX_AI_PROJECT=essential-topic-433910-r5
VERTEX_AI_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_GENAI_USE_VERTEXAI=true

RAZORPAY_KEY_ID=rzp_test_SZkWuoOSwjfZ1k
RAZORPAY_KEY_SECRET=ZermvGnEfYsQu4FeRYtayZhc
RAZORPAY_MODE=test

REDIS_URL=redis://localhost:6379/0
GOOGLE_MAPS_API_KEY=AIzaSyCyAsmPnNkeEr-sxDokti2p8dR7hxkaibY

EMAIL_USER=goyalshikhar67@gmail.com
EMAIL_PASSWORD=uvax aexx bcar lrml

ENABLE_SUPPLIER_API=true
ENABLE_DELIVERY_API=true
ENABLE_SMART_PRICING=true
ENABLE_WHATSAPP_API=true
SUPPLIER_API_URL=
DELIVERY_API_URL=

TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=8d5058479c8514410fe5e35f28c176c1
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_PRESCRIPTION_CONTENT_SID=
EOF
  sudo chown "$APP_USER:$APP_GROUP" "$ENV_FILE"
  sudo chmod 600 "$ENV_FILE"
}

write_systemd_service() {
  log "Writing systemd service"
  sudo tee "$SYSTEMD_FILE" >/dev/null <<EOF
[Unit]
Description=Dr. Kash AI FastAPI service
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python -m uvicorn app.main:app --host ${APP_HOST} --port ${APP_PORT} --proxy-headers
Restart=always
RestartSec=5
TimeoutStartSec=60
TimeoutStopSec=30
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable "${APP_SERVICE}"
}

write_nginx_config() {
  log "Writing Nginx reverse proxy config"
  sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${EXTERNAL_IP} _;

    client_max_body_size 25M;

    location /static/ {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }
}
EOF
  sudo ln -sfn "$NGINX_SITE" "$NGINX_ENABLED"
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl enable nginx
  sudo systemctl restart nginx
}

verify_firewall() {
  log "Verifying local firewall state"
  if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 80/tcp >/dev/null 2>&1 || true
    sudo ufw allow 443/tcp >/dev/null 2>&1 || true
    sudo ufw allow "${APP_PORT}/tcp" >/dev/null 2>&1 || true
    sudo ufw status || true
  else
    log "ufw not installed; relying on GCP VPC firewall rules"
  fi
  log "Ensure GCP ingress allows tcp:80 and tcp:443 to VM ${VM_NAME} in ${ZONE}"
}

install_system_packages() {
  log "Updating apt package index"
  sudo apt-get update -y
  log "Installing system dependencies"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    nginx \
    supervisor \
    curl \
    ca-certificates \
    tesseract-ocr \
    libgl1
}

sync_repo() {
  log "Syncing application source"
  sudo mkdir -p "$APP_DIR"
  sudo chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"

  if [[ ! -d "${APP_DIR}/.git" ]]; then
    sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
  fi

  sudo -u "$APP_USER" git -C "$APP_DIR" remote set-url origin "$REPO_URL"
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch origin
  sudo -u "$APP_USER" git -C "$APP_DIR" checkout main
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only origin main
}

setup_python() {
  log "Setting up virtual environment"
  sudo -u "$APP_USER" mkdir -p "${APP_DIR}/logs" "${APP_DIR}/temp" "${APP_DIR}/backups"
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    sudo -u "$APP_USER" "${PYTHON_BIN}" -m venv "$VENV_DIR"
  fi

  sudo -u "$APP_USER" "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  sudo -u "$APP_USER" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
}

restart_app() {
  log "Restarting application service"
  sudo systemctl restart "${APP_SERVICE}"
}

verify_deployment() {
  log "Running deployment verification"
  sudo systemctl is-active --quiet "${APP_SERVICE}"
  sudo systemctl --no-pager --full status "${APP_SERVICE}" | sed -n '1,20p'

  retry 10 curl -fsS "http://${APP_HOST}:${APP_PORT}/healthz"
  echo
  retry 10 curl -fsS "http://127.0.0.1/healthz"
  echo

  if curl -fsS "http://${EXTERNAL_IP}" >/dev/null; then
    log "External IP check passed: http://${EXTERNAL_IP}"
  else
    log "WARNING: External IP check failed from inside the VM. Service may still be healthy; verify GCP firewall and external routing."
  fi
}

main() {
  require_cmd sudo
  require_cmd git
  require_cmd curl

  log "Starting deployment for ${VM_NAME} in project ${PROJECT_ID}"
  install_system_packages
  sync_repo
  setup_python
  write_env_file
  write_systemd_service
  write_nginx_config
  verify_firewall
  restart_app
  verify_deployment
  log "Deployment completed successfully"
}

main "$@"
