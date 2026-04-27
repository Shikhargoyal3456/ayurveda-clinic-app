#!/bin/bash
set -euo pipefail

echo "Deploying Ayurveda Superapp..."

git pull origin main
docker compose down
docker compose build
docker compose up -d
docker compose exec web python scripts/migrate.py
docker compose exec redis redis-cli FLUSHALL || true
docker compose exec nginx nginx -s reload || true

echo "Deployment complete."
