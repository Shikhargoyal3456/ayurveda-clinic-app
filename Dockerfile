FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    STARTUP_RAG_WARMUP=false \
    STARTUP_LLM_WARMUP=false

WORKDIR /app

COPY requirements-railway.txt /app/requirements-railway.txt
RUN pip install --upgrade pip && pip install -r /app/requirements-railway.txt

COPY . /app

CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]
