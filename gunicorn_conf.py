import multiprocessing


workers = max(2, min(4, multiprocessing.cpu_count()))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
