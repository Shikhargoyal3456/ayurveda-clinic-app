#!/bin/bash
set -euo pipefail

# KASH-AI-DEPLOY-FINAL: One-command Kash AI Cloud Run deployment.
PROJECT_ID="${PROJECT_ID:-your-kash-ai-gcp-project}"
SERVICE_NAME="${SERVICE_NAME:-kash-ai}"
DOMAIN="${DOMAIN:-kashai.in}"
REGION="${REGION:-us-central1}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "KASH AI v1.0 -> PRODUCTION LIVE"

if [ "$PROJECT_ID" = "your-kash-ai-gcp-project" ]; then
  echo "Set PROJECT_ID first: PROJECT_ID=your-real-gcp-project ./deploy.sh"
  exit 1
fi

if [ ! -f ".env.production" ]; then
  echo ".env.production missing. Create it from .env.production.example or the checked-in template."
  exit 1
fi

echo "Testing..."
pytest -v

echo "Migrating local/deploy database..."
python scripts/migrate.py

echo "Building and pushing container..."
gcloud builds submit --tag "$IMAGE"

echo "Deploying to Cloud Run..."
# KASH-AI-DEPLOY-FINAL: Load non-comment production env values from .env.production.
ENV_VARS="$(grep -v '^#' .env.production | grep '=' | sed 's/[[:space:]]*#.*$//' | xargs | tr ' ' ',')"
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --memory 512Mi \
  --concurrency 80 \
  --max-instances 10 \
  --cpu 1 \
  --set-env-vars "$ENV_VARS" \
  --allow-unauthenticated \
  --ingress all \
  --tag "$DOMAIN"

echo "Mapping ${DOMAIN}..."
gcloud run domains add-managed "$DOMAIN" "$SERVICE_NAME" --region "$REGION" || true
gcloud run domain-mappings create --service "$SERVICE_NAME" --domain "$DOMAIN" --region "$REGION" || true
echo "DNS records:"
gcloud run domain-mappings describe "$DOMAIN" --region "$REGION" --format="table(status.resourceRecords)" || true

echo "Smoke testing production..."
sleep 30
URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')"
curl -f "$URL/healthz"
python scripts/smoke.py --base-url "$URL"

echo "KASH AI LIVE TARGET: https://${DOMAIN}/healthz"
echo "Add the DNS records above at your registrar, then wait 5-60 minutes."
echo "Monitor: gcloud logs tail --service=${SERVICE_NAME} --region=${REGION}"
