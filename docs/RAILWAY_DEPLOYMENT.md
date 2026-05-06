# Railway Deployment

This app is prepared to deploy on Railway using the root `Dockerfile`.

## What was blocking deployment earlier

- The app could fail during startup because optional AI/PDF modules were imported too early.
- `app.health` imported the RAG engine at module load time.
- `app.main` imported `app.pdf_loader` just to create directories, which could fail if RAG/PDF extras were missing.
- `routes/prescription.py` imported `fitz` at module load time.
- `requirements.txt` includes several very heavy local-only packages that are not needed for the first public Railway launch.

Those startup blockers are now softened so the app can boot and report a degraded optional feature instead of crashing the whole service.

## Railway setup

1. Push this repo to GitHub.
2. In Railway, create a new project.
3. Choose `Deploy from GitHub repo`.
4. Select this repository.
5. Railway will detect the `Dockerfile` and build from it.

## Required Railway variables

Set these in Railway before or right after the first deploy:

- `ENVIRONMENT=production`
- `SECRET_KEY=<long-random-secret>`
- `SESSION_HTTPS_ONLY=true`
- `HTTPS_REDIRECT_ENABLED=true`
- `REQUIRE_HTTPS_IN_PRODUCTION=true`
- `DATABASE_URL=<Railway Postgres connection string or SQLite fallback if only testing>`
- `PORT=8000`

Recommended:

- `RAZORPAY_KEY_ID=...`
- `RAZORPAY_KEY_SECRET=...`
- `GEMINI_API_KEY=...`
- `GROQ_API_KEY=...`
- `SENTRY_DSN=...`
- `CONTACT_EMAIL_USER=goyalshikhar67@gmail.com`
- `CONTACT_EMAIL_PASSWORD=<gmail-app-password>`
- `TRUSTED_HOSTS=<your-railway-domain>,<your-custom-domain>,127.0.0.1,localhost,testserver`
- `ALLOWED_ORIGINS=https://<your-railway-domain>,https://<your-custom-domain>`

Safe first-launch flags:

- `STARTUP_RAG_WARMUP=false`
- `STARTUP_LLM_WARMUP=false`
- `AI_ENABLED=true`

## Database recommendation

For any client or investor demo, use Railway Postgres instead of SQLite.

In Railway:

1. Add a PostgreSQL service.
2. Copy the provided connection string.
3. Set it as `DATABASE_URL` on the web service.

## How to get a shareable link

After the deploy is healthy:

1. Open your Railway service.
2. Go to `Settings`.
3. Open `Networking`.
4. Under `Public Networking`, click `Generate Domain`.
5. Railway will create a public `*.up.railway.app` URL.

That URL is your first shareable app link for users, clients, and investors.

## Custom domain later

When you want a branded link:

1. In the same `Networking` section, click `+ Custom Domain`.
2. Enter your domain or subdomain.
3. Add the Railway-provided `CNAME` and verification `TXT` records in your DNS provider.
4. Wait for Railway to verify it and issue SSL.

## First smoke checks after deploy

Open these paths:

- `/health`
- `/contact`
- `/auth/login`
- `/portal`
- `/order-medicines`

If `/health` returns `200`, Railway should mark the deployment healthy.

## Notes

- Railway does not make a service public automatically. You must generate a domain.
- Railway health checks use the service `PORT` and wait for `/health` to return `200`.
- If a deploy fails, check the deployment logs first for missing environment variables or database connection issues.
