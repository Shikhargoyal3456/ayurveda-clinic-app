#!/usr/bin/env bash
set -euo pipefail

VM_NAME="kash-ai-prod"
ZONE="asia-south1-b"
REMOTE_ROOT="${REMOTE_ROOT:-~/ayurveda_project}"
SERVICE_NAME="${SERVICE_NAME:-ayurveda-clinic}"
ENABLE_NGINX="${ENABLE_NGINX:-false}"

echo "Deploying Dr. Kash AI files to ${VM_NAME} (${ZONE})"

gcloud compute scp "routers/ai_doctor.py" "${VM_NAME}:${REMOTE_ROOT}/routers/ai_doctor.py" --zone "${ZONE}"
gcloud compute scp "static/js/doctor.js" "${VM_NAME}:${REMOTE_ROOT}/static/js/doctor.js" --zone "${ZONE}"
gcloud compute scp "templates/doctor.html" "${VM_NAME}:${REMOTE_ROOT}/templates/doctor.html" --zone "${ZONE}"
gcloud compute scp "app/main.py" "${VM_NAME}:${REMOTE_ROOT}/app/main.py" --zone "${ZONE}"
gcloud compute scp "app/security.py" "${VM_NAME}:${REMOTE_ROOT}/app/security.py" --zone "${ZONE}"

gcloud compute ssh "${VM_NAME}" --zone "${ZONE}" --command "
set -e
cd ${REMOTE_ROOT}
chmod 644 routers/ai_doctor.py static/js/doctor.js templates/doctor.html app/main.py app/security.py
sudo systemctl daemon-reload
sudo systemctl restart ${SERVICE_NAME}
sudo systemctl --no-pager --full status ${SERVICE_NAME} | head -n 20
curl -fsS http://127.0.0.1:8000/api/doctor/health
curl -fsS http://127.0.0.1:8000/ai-doctor-live >/dev/null
"

if [[ \"${ENABLE_NGINX}\" == \"true\" ]]; then
  gcloud compute ssh "${VM_NAME}" --zone "${ZONE}" --command "
set -e
sudo apt-get update
sudo apt-get install -y nginx
sudo tee /etc/nginx/sites-available/kash-ai >/dev/null <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_read_timeout 120s;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/kash-ai /etc/nginx/sites-enabled/kash-ai
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
curl -fsS http://127.0.0.1/api/doctor/health
"
fi

echo "Deployment complete."
