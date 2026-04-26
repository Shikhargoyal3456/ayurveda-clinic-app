#!/bin/bash
set -euo pipefail

# KASH-AI-DEPLOY-FINAL: Managed Cloud Run domain mapping helper for kashai.in.
SERVICE="${SERVICE:-kash-ai}"
DOMAIN="${DOMAIN:-kashai.in}"
REGION="${REGION:-us-central1}"

echo "Mapping ${DOMAIN} to Cloud Run service ${SERVICE} in ${REGION}"
gcloud run domains add-managed "${DOMAIN}" "${SERVICE}" --region "${REGION}" || true
gcloud run domain-mappings create --service "${SERVICE}" --domain "${DOMAIN}" --region "${REGION}" || true
echo "DNS records:"
gcloud run domain-mappings describe "${DOMAIN}" --region "${REGION}" --format="table(status.resourceRecords)" || true
echo "Add the records above at your registrar."
echo "Wait 5-60 minutes, then test: https://${DOMAIN}/healthz"
