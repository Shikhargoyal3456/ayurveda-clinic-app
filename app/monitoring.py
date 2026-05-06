from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.slow_request_count = 0

    def record_request(self, duration_seconds: float, is_error: bool = False, is_slow: bool = False) -> None:
        with self._lock:
            self.request_count += 1
            self.total_response_time += duration_seconds
            if is_error:
                self.error_count += 1
            if is_slow:
                self.slow_request_count += 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            avg_seconds = self.total_response_time / self.request_count if self.request_count else 0.0
            error_rate = (self.error_count / self.request_count * 100.0) if self.request_count else 0.0
            return {
                "total_requests": self.request_count,
                "error_count": self.error_count,
                "slow_request_count": self.slow_request_count,
                "error_rate": round(error_rate, 2),
                "avg_response_time_ms": round(avg_seconds * 1000, 2),
            }


metrics = MetricsCollector()


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start_time
            status_code = getattr(response, "status_code", 500)
            is_slow = duration > 1.0
            if is_slow:
                logger.warning("Slow request: %s %s took %.2fs", request.method, request.url.path, duration)
            metrics.record_request(duration, is_error=status_code >= 500, is_slow=is_slow)
            if response is not None:
                response.headers["X-Response-Time"] = f"{duration:.3f}s"
