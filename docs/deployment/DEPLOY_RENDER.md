# Render Deployment Guide

This app is prepared for deployment to Render as a Python web service backed by Render Postgres.

## Files added for Render

- `render.yaml`
- `runtime.txt`
- `.env.render.example`
- `.github/workflows/render-deploy.yml`
- `deploy_render.sh`

## Render service type

- Runtime: Python
- Start command: `gunicorn app.main:app -c gunicorn_conf.py`
- Health check: `/health`
- Python version: `3.11.11`

## Important production notes

1. Do not use SQLite on Render for real app data. Render free web services have an ephemeral filesystem.
2. The included `render.yaml` provisions a free Render Postgres database and wires `DATABASE_URL` automatically.
3. `REDIS_URL` is intentionally blank by default because the app degrades safely without Redis.
4. Free Render services can spin down after inactivity and cold start on the next request.
5. Free Render Postgres databases expire after 30 days unless upgraded.

## Deploy steps

1. Push this repository to GitHub.
2. In Render, choose `New +` -> `Blueprint`.
3. Connect your GitHub repo and select this repository.
4. Render will read `render.yaml` and propose:
   - one web service
   - one Postgres database
5. Before finishing setup, provide the `sync: false` variables in the Render dashboard:
   - `TRUSTED_HOSTS`
   - `ALLOWED_ORIGINS`
   - `ADMIN_USERNAMES`
   - `GEMINI_API_KEY` and/or `GROQ_API_KEY`
   - `GOOGLE_MAPS_API_KEY`
   - `GOOGLE_SPEECH_API_KEY`
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`
   - optional WhatsApp and email variables
6. Deploy.

## Recommended initial values

- `TRUSTED_HOSTS=your-service.onrender.com`
- `ALLOWED_ORIGINS=https://your-service.onrender.com`
- `ALLOW_PUBLIC_SIGNUP=false` after the first admin account is created
- `RAZORPAY_MODE=test` until payments are validated

## Post-deploy checks

Open these URLs after the first deploy:

- `/health`
- `/healthz`
- `/api/ai/status`

## Migrations

If you need to run schema migrations manually:

```bash
alembic upgrade head
```

If you prefer to add migration execution to the build step later, update `render.yaml` carefully so startup stays fast.
