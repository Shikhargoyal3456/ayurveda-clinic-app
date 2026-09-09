#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:-essential-topic-433910-r5}"
REGION="${REGION:-asia-south1}"
SERVICE_NAME="${SERVICE_NAME:-kash-ai}"
REPOSITORY="${REPOSITORY:-kash-ai-repo}"
IMAGE_NAME="${IMAGE_NAME:-kash-ai}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-kash-ai-runner}"
MIGRATION_JOB_NAME="${MIGRATION_JOB_NAME:-kash-ai-migrate}"
ENV_FILE="${ENV_FILE:-.env}"
CLOUD_SQL_INSTANCE_NAME="${CLOUD_SQL_INSTANCE_NAME:-kash-ai-db}"

log() {
  printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$1"
}

retry() {
  local attempts="$1"
  shift
  local count=1
  until "$@"; do
    if [[ "$count" -ge "$attempts" ]]; then
      return 1
    fi
    sleep $((count * 3))
    count=$((count + 1))
    log "Retrying command: $*"
  done
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

require_command gcloud
require_command docker

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

log "Enabling required GCP APIs..."
retry 3 gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com sqladmin.googleapis.com aiplatform.googleapis.com --project "$PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null

if ! gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating Artifact Registry repository $REPOSITORY..."
  retry 3 gcloud artifacts repositories create "$REPOSITORY" --project "$PROJECT_ID" --location "$REGION" --repository-format docker --description "Dr. Kash AI production images"
fi

RUNTIME_SA="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$RUNTIME_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  log "Creating service account $RUNTIME_SA..."
  retry 3 gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" --project "$PROJECT_ID" --display-name "Dr. Kash AI Cloud Run runtime"
fi

retry 3 gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

log "Building Docker image..."
docker build -t "$IMAGE_URI" -t "$LATEST_URI" .
log "Pushing Docker image..."
docker push "$IMAGE_URI"
docker push "$LATEST_URI"

declare -A ENV_MAP
while IFS= read -r raw_line; do
  line="${raw_line#"${raw_line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  ENV_MAP["$key"]="$value"
done < "$ENV_FILE"

PLAIN_ENV_KEYS=(
  APP_ENV APP_NAME APP_VERSION ENVIRONMENT DEBUG HOST PORT UVICORN_RELOAD GOOGLE_REDIRECT_URI
  PILOT_BYPASS_SUBSCRIPTIONS SESSION_HTTPS_ONLY CSRF_ENABLED GOOGLE_GENAI_USE_VERTEXAI
  RAZORPAY_MODE ALLOWED_ORIGINS TRUSTED_HOSTS RATE_LIMIT_ENABLED RATE_LIMIT_REQUESTS RATE_LIMIT_PERIOD
  API_IP_RATE_LIMIT_REQUESTS API_IP_RATE_LIMIT_PERIOD API_USER_RATE_LIMIT_REQUESTS API_USER_RATE_LIMIT_PERIOD
  MAX_CONCURRENT_REQUESTS OVERLOAD_QUEUE_TIMEOUT_SECONDS CACHE_ENABLED CACHE_TTL BACKUP_ENABLED
  BACKUP_RETENTION_DAYS CLOUD_RUN_MEMORY CLOUD_RUN_CONCURRENCY HTTPS_REDIRECT_ENABLED REQUIRE_HTTPS_IN_PRODUCTION
)

TMP_ENV_FILE="$(mktemp)"
SECRET_BINDINGS=()
trap 'rm -f "$TMP_ENV_FILE"' EXIT

contains_plain_env() {
  local needle="$1"
  for item in "${PLAIN_ENV_KEYS[@]}"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

for key in "${!ENV_MAP[@]}"; do
  value="${ENV_MAP[$key]}"
  [[ -z "$value" ]] && continue
  if contains_plain_env "$key"; then
    escaped="${value//\'/\'\'}"
    printf "%s: '%s'\n" "$key" "$escaped" >> "$TMP_ENV_FILE"
  else
    secret_name="$(echo "$key" | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
    if gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
      SECRET_BINDINGS+=("${key}=${secret_name}:latest")
    fi
  fi
done

CLOUD_SQL_CONNECTION="${PROJECT_ID}:${REGION}:${CLOUD_SQL_INSTANCE_NAME}"
if gcloud sql instances describe "$CLOUD_SQL_INSTANCE_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  retry 3 gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${RUNTIME_SA}" --role roles/cloudsql.client >/dev/null
  CLOUD_SQL_FLAG=(--add-cloudsql-instances "$CLOUD_SQL_CONNECTION")
  CLOUD_SQL_JOB_FLAG=(--set-cloudsql-instances "$CLOUD_SQL_CONNECTION")
else
  CLOUD_SQL_FLAG=()
  CLOUD_SQL_JOB_FLAG=()
fi

JOB_DEPLOY_ARGS=(
  run jobs deploy "$MIGRATION_JOB_NAME"
  --project "$PROJECT_ID"
  --region "$REGION"
  --image "$IMAGE_URI"
  --service-account "$RUNTIME_SA"
  --memory 1Gi
  --cpu 1
  --task-timeout 300
  --max-retries 1
  --command alembic
  --args upgrade,head
  --env-vars-file "$TMP_ENV_FILE"
  "${CLOUD_SQL_JOB_FLAG[@]}"
)

if ((${#SECRET_BINDINGS[@]} > 0)); then
  JOB_DEPLOY_ARGS+=(--set-secrets "$(IFS=,; echo "${SECRET_BINDINGS[*]}")")
fi

retry 3 gcloud "${JOB_DEPLOY_ARGS[@]}"

retry 3 gcloud run jobs execute "$MIGRATION_JOB_NAME" --project "$PROJECT_ID" --region "$REGION" --wait

DEPLOY_ARGS=(
  run deploy "$SERVICE_NAME"
  --project "$PROJECT_ID"
  --region "$REGION"
  --platform managed
  --image "$IMAGE_URI"
  --service-account "$RUNTIME_SA"
  --allow-unauthenticated
  --port 8080
  --memory 1Gi
  --cpu 1
  --concurrency 80
  --timeout 300
  --env-vars-file "$TMP_ENV_FILE"
  "${CLOUD_SQL_FLAG[@]}"
)

if ((${#SECRET_BINDINGS[@]} > 0)); then
  DEPLOY_ARGS+=(--set-secrets "$(IFS=,; echo "${SECRET_BINDINGS[*]}")")
fi

retry 3 gcloud "${DEPLOY_ARGS[@]}"

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
log "Cloud Run URL: $SERVICE_URL"

curl --fail --silent --show-error "$SERVICE_URL/health" >/dev/null
curl --fail --silent --show-error "$SERVICE_URL/static/images/favicon.svg" >/dev/null

if [[ -n "${ENV_MAP[GOOGLE_CLIENT_ID]:-}" && -n "${ENV_MAP[GOOGLE_CLIENT_SECRET]:-}" ]]; then
  curl --silent --show-error --head --max-redirs 0 "$SERVICE_URL/auth/google/login" >/dev/null || true
fi

if [[ -n "${ENV_MAP[VERTEX_AI_PROJECT]:-}" && -n "${ENV_MAP[VERTEX_AI_LOCATION]:-}" && -n "${ENV_MAP[GEMINI_MODEL]:-}" ]]; then
  ACCESS_TOKEN="$(gcloud auth print-access-token)"
  curl --fail --silent --show-error \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST \
    "https://${ENV_MAP[VERTEX_AI_LOCATION]}-aiplatform.googleapis.com/v1/projects/${ENV_MAP[VERTEX_AI_PROJECT]}/locations/${ENV_MAP[VERTEX_AI_LOCATION]}/publishers/google/models/${ENV_MAP[GEMINI_MODEL]}:generateContent" \
    -d '{"contents":[{"role":"user","parts":[{"text":"Reply with OK"}]}]}' >/dev/null
fi

log "Deployment completed successfully."
