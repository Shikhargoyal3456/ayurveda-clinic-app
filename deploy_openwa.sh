#!/bin/bash
set -euo pipefail

# Deploy OpenWA on a GCP VM with local SQLite storage.

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  sudo usermod -aG docker "$USER"
fi

if [ ! -d OpenWA ]; then
  git clone https://github.com/rmyndharis/OpenWA.git
fi

cd OpenWA
mkdir -p data/sessions data/media

cat > .env <<'EOF'
PORT=2785
NODE_ENV=production
DATABASE_TYPE=sqlite
DATABASE_NAME=/app/data/openwa.sqlite
ENGINE_TYPE=whatsapp-web.js
SESSION_DATA_PATH=/app/data/sessions
STORAGE_TYPE=local
STORAGE_LOCAL_PATH=/app/data/media
REDIS_ENABLED=false
WEBHOOK_TIMEOUT=10000
WEBHOOK_MAX_RETRIES=3
RATE_LIMIT_TTL=60
RATE_LIMIT_MAX=100
PLUGINS_ENABLED=false
API_MASTER_KEY=owa_k1_KashAI_2026_Secret
EOF

docker compose up -d

echo "OpenWA running at http://$(hostname -I | awk '{print $1}'):2785"
echo "API Key: owa_k1_KashAI_2026_Secret"
