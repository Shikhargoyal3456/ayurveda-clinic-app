from collections import defaultdict
import time
from starlette.responses import JSONResponse
from app.config import settings


class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute=60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        if not getattr(settings, "rate_limit_enabled", True):
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if path in ["/healthz", "/api/voice/health", "/favicon.ico"]:
            return await self.app(scope, receive, send)

        # Do not throttle static files or Vite assets in development
        if path.startswith(("/static", "/shared-static", "/@vite", "/@react-refresh", "/src", "/node_modules")):
            return await self.app(scope, receive, send)

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # Allow generous limit for localhost / development
        limit = self.requests_per_minute
        if not getattr(settings, "is_production", False) or client_ip in ("127.0.0.1", "::1", "localhost", "testserver"):
            limit = max(limit, getattr(settings, "rate_limit_requests", 300), 300)

        now = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]

        if len(self.requests[client_ip]) >= limit:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later.", "retry_after": 60},
                headers={"Retry-After": "60"},
            )
            return await response(scope, receive, send)

        self.requests[client_ip].append(now)
        return await self.app(scope, receive, send)

