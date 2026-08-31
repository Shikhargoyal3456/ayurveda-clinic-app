# Kash AI - Deployment Guide

## Production Targets

- Frontend landing page: `https://kash-ai.vercel.app`
- Backend API: `https://kash-ai-api.onrender.com`
- Database: Render PostgreSQL internal connection string

## Important Secret Handling

Do not commit API keys, database URLs, JWT secrets, encryption keys, or session secrets. Add them only in the hosting provider environment variable UI. If any real API keys have been shared in prompts, chat logs, screenshots, or committed files, rotate them before production launch.

## Version Control

The repository is already initialized with Git. Before committing, review the dirty working tree and stage only intentional production files:

```powershell
git status --short
git add .gitignore vercel.json index.html DEPLOYMENT.md
git add templates static routers app requirements.txt
git commit -m "Prepare Kash AI production deployment"
```

Push after creating a GitHub repository:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/kash-ai.git
git branch -M main
git push -u origin main
```

## Vercel Frontend

This repo includes `vercel.json` for a static landing page deployment from `index.html`.

Deploy:

```powershell
npm install -g vercel
vercel --prod
```

The static landing CTA points to:

```text
https://kash-ai-api.onrender.com
```

## Render Backend

Create a Render Web Service connected to the GitHub repo:

- Name: `kash-ai-api`
- Environment: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 10000`

Set production environment variables in Render:

```text
ENVIRONMENT=production
DEBUG=False
DATABASE_URL=<render-postgresql-internal-url>
GROQ_API_KEY=<rotated-groq-key>
GEMINI_API_KEY=<rotated-gemini-key>
SECRET_KEY=<strong-random-secret>
JWT_SECRET=<strong-random-secret>
ENCRYPTION_KEY=<strong-random-secret>
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
ALLOWED_ORIGINS=https://kash-ai.vercel.app,https://kash-ai-api.onrender.com
```

## Render PostgreSQL

Create a Render PostgreSQL database:

- Name: `kash-ai-db`
- Plan: Free tier for initial validation
- Copy the internal connection string into `DATABASE_URL`

## Post-Deployment Verification

```powershell
curl https://kash-ai-api.onrender.com/healthz
curl https://kash-ai-api.onrender.com/feature-status
curl https://kash-ai-api.onrender.com/api/voice/health
```

Checklist:

- [ ] GitHub repository created
- [ ] Intentional files committed and pushed
- [ ] Vercel frontend deployed
- [ ] Render backend deployed
- [ ] Render PostgreSQL created
- [ ] Production secrets set in Render
- [ ] Landing page CTA opens backend
- [ ] Health check returns 200
- [ ] Login page loads
- [ ] Voice and feature status pages work

---

# Dr. Kash AI Deployment on Google Cloud Platform

This deployment bundle is designed for your project:

- Project: `essential-topic-433910-r5`
- Cloud Run service: `kash-ai`
- Artifact Registry repository: `kash-ai-repo`
- Optional Cloud SQL instance: `kash-ai-db`
- Recommended region: `asia-south1`

The easiest Windows path is one command:

```powershell
pwsh -File .\deploy-cloud-run.ps1 -SetupSecrets -SetupCloudSql
```

That command can:

1. Enable required GCP APIs
2. Create or update Secret Manager secrets from `.env`
3. Create or update the optional Cloud SQL PostgreSQL instance
4. Build and push the Docker image to Artifact Registry
5. Run Alembic migrations in a Cloud Run Job
6. Deploy Cloud Run
7. Verify health, static files, Google login redirect, and Vertex AI

## Files

- `Dockerfile`: Production container using `python:3.11-slim`, Gunicorn, Uvicorn workers, and `/health` health check
- `.dockerignore`: Keeps the build context small and excludes secrets
- `deploy-cloud-run.ps1`: Windows all-in-one deployment script
- `deploy-cloud-run.sh`: Bash deployment script for Linux and macOS
- `setup-secrets.ps1`: Reads `.env`, stores secrets in Secret Manager, and grants access
- `setup-cloud-sql.ps1`: Creates PostgreSQL 15, database, user, and `DATABASE_URL`
- `cloudbuild.yaml`: CI/CD image build and redeploy for later releases

## Prerequisites

Install and authenticate:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project essential-topic-433910-r5
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

Recommended local tools:

- Docker Desktop
- PowerShell 7+
- `curl`

## Recommended Deployment Flow

### Option 1: One command on Windows

```powershell
pwsh -File .\deploy-cloud-run.ps1 -SetupSecrets -SetupCloudSql
```

### Option 2: Step by step on Windows

1. Set up secrets:

```powershell
pwsh -File .\setup-secrets.ps1
```

2. Set up PostgreSQL:

```powershell
pwsh -File .\setup-cloud-sql.ps1
```

3. Deploy:

```powershell
pwsh -File .\deploy-cloud-run.ps1
```

### Option 3: Linux or macOS

This script assumes secrets already exist.

```bash
chmod +x ./deploy-cloud-run.sh
./deploy-cloud-run.sh
```

## What Gets Stored as Secrets

The secret setup script stores the requested secret keys from `.env` and also stores `SECRET_KEY` and `DATABASE_URL` when present, because production boot and secure sessions depend on them.

Examples:

- `VERTEX_AI_PROJECT`
- `VERTEX_AI_LOCATION`
- `GEMINI_MODEL`
- `GOOGLE_GENAI_USE_VERTEXAI`
- `EMAIL_USER`
- `EMAIL_PASSWORD`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GROQ_API_KEY`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_SPEECH_API_KEY`
- `SECRET_KEY`
- `DATABASE_URL`

## Cloud SQL Notes

`setup-cloud-sql.ps1` creates:

- Instance: `kash-ai-db`
- PostgreSQL version: `POSTGRES_15`
- Database: `kash_ai`
- User: `kash_ai_user`

It also prints and optionally stores a Cloud Run friendly SQLAlchemy URL:

```text
postgresql+psycopg2://kash_ai_user:<PASSWORD>@/kash_ai?host=/cloudsql/essential-topic-433910-r5:asia-south1:kash-ai-db
```

## Verification Performed After Deployment

The deploy scripts verify:

1. `GET /health` returns HTTP 200
2. A static asset returns HTTP 200
3. `GET /auth/google/login` returns a redirect when Google auth is configured
4. Vertex AI Gemini responds through the Vertex REST API when ADC is available
5. Alembic migrations complete through the Cloud Run Job

## Useful Commands

Get the Cloud Run URL:

```powershell
gcloud run services describe kash-ai --region asia-south1 --format="value(status.url)"
```

Tail logs:

```powershell
gcloud run services logs tail kash-ai --region asia-south1
```

Run migrations again:

```powershell
gcloud run jobs execute kash-ai-migrate --region asia-south1 --wait
```

Describe secrets:

```powershell
gcloud secrets list
```

## Rollback

List revisions:

```powershell
gcloud run revisions list --service kash-ai --region asia-south1
```

Shift traffic to an older revision:

```powershell
gcloud run services update-traffic kash-ai --region asia-south1 --to-revisions REVISION_NAME=100
```

Redeploy `latest` image if needed:

```powershell
pwsh -File .\deploy-cloud-run.ps1
```

## Troubleshooting

### Health check fails

- Inspect logs: `gcloud run services logs tail kash-ai --region asia-south1`
- Confirm `SECRET_KEY` is set and not using the placeholder value
- Confirm `DATABASE_URL` exists and is reachable

### Google login returns 503

- Confirm `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` exist in Secret Manager
- Update `GOOGLE_REDIRECT_URI` in `.env` to your actual Cloud Run callback URL:
  `https://<cloud-run-url>/auth/google/callback`
- Add the same callback URL to the Google OAuth client in Google Cloud Console

### Vertex AI verification fails

- Run `gcloud auth application-default login`
- Confirm the Vertex API is enabled
- Confirm the model and region in `.env` are valid for your project

### Database migration job fails

- Inspect job logs:

```powershell
gcloud run jobs executions list --job kash-ai-migrate --region asia-south1
```

- Confirm the Cloud SQL instance exists
- Confirm `DATABASE_URL` points to `/cloudsql/PROJECT:REGION:INSTANCE`
- Confirm the Cloud Run runtime service account has `Cloud SQL Client`

### Static files fail to load

- Confirm the Docker image contains `static/` and `templates/`
- Retry deployment after a fresh image build

## CI/CD

After the initial bootstrap, you can redeploy from source with Cloud Build:

```powershell
gcloud builds submit --config cloudbuild.yaml
```

This CI/CD path is intended for later image-only redeploys after secrets and base infrastructure are already in place.
