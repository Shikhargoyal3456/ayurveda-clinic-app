#!/usr/bin/env bash
set -euo pipefail

# KASH-AI-PROD-SETUP: Reserve Kash AI's external IP and report VM attachment status.
REGION="${REGION:-asia-south1}"
ZONE="${ZONE:-asia-south1-b}"
INSTANCE="${INSTANCE:-instance-20260318-164709}"
ADDRESS_NAME="${ADDRESS_NAME:-kash-ai-ip}"
STATIC_IP="${STATIC_IP:-34.93.71.25}"

echo "Reserving static IP for Kash AI"
echo "Region: ${REGION}"
echo "Zone: ${ZONE}"
echo "Instance: ${INSTANCE}"
echo "Address: ${ADDRESS_NAME} -> ${STATIC_IP}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed or not on PATH."
  exit 1
fi

if gcloud compute addresses describe "${ADDRESS_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo "Static address ${ADDRESS_NAME} already exists."
else
  gcloud compute addresses create "${ADDRESS_NAME}" \
    --region "${REGION}" \
    --addresses "${STATIC_IP}"
fi

CURRENT_IP="$(gcloud compute instances describe "${INSTANCE}" \
  --zone "${ZONE}" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)' || true)"

echo "Instance current external IP: ${CURRENT_IP:-none}"

if [[ "${CURRENT_IP}" == "${STATIC_IP}" ]]; then
  echo "Instance already uses ${STATIC_IP}. Nothing else to do."
  exit 0
fi

if [[ -n "${CURRENT_IP}" && "${APPLY_STATIC_IP_CHANGE:-false}" != "true" ]]; then
  echo "The instance currently has a different external IP."
  echo "To replace it with ${STATIC_IP}, rerun with APPLY_STATIC_IP_CHANGE=true."
  echo "Warning: replacing the access config can briefly interrupt SSH."
  exit 2
fi

if [[ -n "${CURRENT_IP}" ]]; then
  gcloud compute instances delete-access-config "${INSTANCE}" \
    --zone "${ZONE}" \
    --access-config-name "External NAT" || true
fi

gcloud compute instances add-access-config "${INSTANCE}" \
  --zone "${ZONE}" \
  --access-config-name "External NAT" \
  --address "${STATIC_IP}"

echo "Static IP attached."
