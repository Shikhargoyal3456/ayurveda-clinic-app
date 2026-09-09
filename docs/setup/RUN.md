# Running Kash AI

Quick-start for getting the Kash AI platform running locally and in production.
For in-depth deployment, infrastructure, and operations guidance see
[DEPLOYMENT.md](DEPLOYMENT.md) and [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).

---

## Prerequisites

- **Python 3.11+** (the production image builds on 3.11–3.13)
- A database (SQLite works out of the box for local dev; Postgres recommended for production — set `DATABASE_URL`)
- Optional: Docker + Docker Compose for containerized runs

---

## Local development (5 steps)

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate            # Windows: .\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your environment file and set a secret
cp .env.example .env
#    then edit .env — at minimum set SECRET_KEY (and DATABASE_URL if not using SQLite)

# 4. Apply database migrations
alembic upgrade head

# 5. Start the dev server (auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** — the public landing (`/`) redirects to the Kash AI
frontend at `/new`. The API entrypoint is the ASGI app `app.main:app`.

> **First account:** create the first doctor via `/signup` while
> `ALLOW_PUBLIC_SIGNUP=true`, then set it to `false` in `.env`.

---

## Production

Run under Gunicorn with Uvicorn workers (config in `gunicorn_conf.py`):

```bash
export ENVIRONMENT=production
pip install -r requirements.txt
alembic upgrade head
gunicorn -c gunicorn_conf.py -b 0.0.0.0:8000 app.main:app
```

- Workers default to a CPU-derived count; override with `WEB_CONCURRENCY`.
- Worker class is `uvicorn.workers.UvicornWorker`.
- Bind port comes from `PORT` (default `8000`).

### Docker

```bash
# Production image (multi-stage, non-root, healthcheck on /healthz)
docker build -f Dockerfile.prod -t kash-ai:prod .
docker run --env-file .env -p 8000:8000 kash-ai:prod

# Or with compose
docker compose -f docker-compose.prod.yml up -d
```

---

## Configuration

All settings are read from environment variables (see `.env.example`, ~77 keys).
The most important ones to review before going live:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Session/CSRF signing — **must** be set to a long random value |
| `ENVIRONMENT` | `development` or `production` (enables HTTPS redirect, disables warmups, etc.) |
| `DATABASE_URL` | Database connection string (defaults to local SQLite if unset) |
| `ALLOW_PUBLIC_SIGNUP` | Gate open registration on/off |
| `HOST` / `PORT` | Bind address (defaults `0.0.0.0:8000`) |

Validate your environment at any time:

```bash
python verify_environment.py
```

---

## Health & status endpoints

| Endpoint | Description |
|---|---|
| `/healthz` | Detailed health check (used by the Docker healthcheck) |
| `/api/ai/status` | AI subsystem status (model / fallback mode) |
| `/api/admin/metrics` | Admin metrics (authenticated) |

---

## Tests

```bash
pytest -q
# Windows helper:
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
```
