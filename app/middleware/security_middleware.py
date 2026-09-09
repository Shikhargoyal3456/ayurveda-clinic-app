from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.security_config import security_settings


class RateLimiter:
    def __init__(self) -> None:
        self.requests = defaultdict(list)
        self.login_attempts = defaultdict(list)

    def check_rate_limit(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.time()
        entries = self.requests[key]
        self.requests[key] = [entry for entry in entries if now - entry < window]
        if len(self.requests[key]) >= limit:
            return False
        self.requests[key].append(now)
        return True

    def login_allowed(self, key: str) -> bool:
        return self.check_rate_limit(key, security_settings.login_rate_limit, 900)


rate_limiter = RateLimiter()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)")
        response.headers.setdefault("Content-Security-Policy", security_settings.csp_policy)
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if request.url.path.startswith("/auth/login"):
            allowed = rate_limiter.login_allowed(f"login:{client_ip}")
            if not allowed:
                return JSONResponse(status_code=429, content={"detail": "Too many login attempts. Please wait and try again."})
        allowed = rate_limiter.check_rate_limit(f"ip:{client_ip}", security_settings.rate_limit_per_ip, 60)
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
        return await call_next(request)
