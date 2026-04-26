#!/usr/bin/env bash
set -euo pipefail

# KASH-AI-PROD-SETUP: Idempotent VM production setup for kashai.in.
DOMAIN="${DOMAIN:-kashai.in}"
APP_PORT="${APP_PORT:-8000}"
SERVICE_NAME="${SERVICE_NAME:-ayurveda-clinic}"
CERT_EMAIL="${CERT_EMAIL:-shikhar@kash.ai}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NGINX_SITE="/etc/nginx/sites-available/kash-ai"
HEALTH_SERVICE="/etc/systemd/system/kash-health.service"
HEALTH_TIMER="/etc/systemd/system/kash-health.timer"

echo "Kash AI VM production setup"
echo "Domain: ${DOMAIN}"
echo "App service: ${SERVICE_NAME}"
echo "App port: ${APP_PORT}"
echo "Project root: ${PROJECT_ROOT}"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run this script as the app user, not root. It will use sudo where needed."
  exit 1
fi

echo "Installing Nginx, Certbot, and curl..."
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx curl

echo "Writing Nginx reverse proxy..."
sudo tee "${NGINX_SITE}" >/dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    client_max_body_size 20m;

    location = / {
        proxy_pass http://127.0.0.1:${APP_PORT}/static/index.html;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        expires 1d;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
EOF

sudo ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/kash-ai
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "Reloading and restarting app service..."
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "Checking local app health..."
curl -fsS "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null || curl -fsS "http://127.0.0.1:${APP_PORT}/" >/dev/null

echo "Installing health monitor service and timer..."
sudo tee "${HEALTH_SERVICE}" >/dev/null <<EOF
[Unit]
Description=Kash AI Health Check
After=network-online.target ${SERVICE_NAME}.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'curl -fsS http://127.0.0.1:${APP_PORT}/healthz >/dev/null || (systemctl restart ${SERVICE_NAME} && sleep 8 && curl -fsS http://127.0.0.1:${APP_PORT}/healthz >/dev/null)'
EOF

sudo tee "${HEALTH_TIMER}" >/dev/null <<EOF
[Unit]
Description=Run Kash AI Health Check every minute

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
Unit=kash-health.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kash-health.timer

echo "Requesting/renewing Let's Encrypt certificate..."
if [[ "${SKIP_SSL:-false}" != "true" ]]; then
  sudo certbot --nginx \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}" \
    --non-interactive \
    --agree-tos \
    -m "${CERT_EMAIL}" \
    --redirect
  sudo systemctl enable certbot.timer
else
  echo "SKIP_SSL=true set; skipping certbot."
fi

echo "Final verification..."
sudo nginx -t
sudo systemctl is-active --quiet "${SERVICE_NAME}"
sudo systemctl is-active --quiet nginx
sudo systemctl list-timers kash-health.timer --no-pager

echo "Kash AI VM setup complete."
echo "Verify:"
echo "  curl -I https://${DOMAIN}"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo systemctl status kash-health.timer"
