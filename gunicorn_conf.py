import multiprocessing
import os


def _default_workers() -> int:
    render_cpu = os.getenv("RENDER_CPU_COUNT", "").strip()
    if render_cpu:
        try:
            return max(2, min(4, int(max(1.0, float(render_cpu)) * 2)))
        except ValueError:
            pass
    return max(2, min(4, multiprocessing.cpu_count()))


workers = int(os.getenv("WEB_CONCURRENCY", str(_default_workers())))
threads = max(1, int(os.getenv("GUNICORN_THREADS", "2")))
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "10"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "45"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
