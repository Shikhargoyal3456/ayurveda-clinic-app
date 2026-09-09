#!/bin/bash
# One-command deployment to Google Cloud Run

set -euo pipefail

echo "Deploying Kash AI to Google Cloud Run..."

if ! command -v gcloud >/dev/null 2>&1; then
    echo "gcloud not found. Please install Google Cloud SDK first."
    exit 1
fi

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
if [ "${PROJECT_ID}" = "(unset)" ] || [ -z "${PROJECT_ID}" ]; then
    echo "No project set. Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "Using project: ${PROJECT_ID}"

echo "Enabling required APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "${PROJECT_ID}"

echo "Building and deploying..."
gcloud run deploy kash-ai \
    --source . \
    --project "${PROJECT_ID}" \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600

URL="$(gcloud run services describe kash-ai --project "${PROJECT_ID}" --region us-central1 --format='value(status.url)')"

echo
echo "Deployment complete."
echo "Your app is live at: ${URL}"
echo
echo "Test with: curl ${URL}/health"
