import multiprocessing


workers = multiprocessing.cpu_count()
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
