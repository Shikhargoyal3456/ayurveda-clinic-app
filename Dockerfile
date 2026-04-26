FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# DEPLOY-FULL-1: Apply migrations at runtime against the real DATABASE_URL, then start Cloud Run.
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
