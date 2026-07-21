from collections import defaultdict
import time
from fastapi import Request, HTTPException


class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute=60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        path = request.url.path

        if path in ["/healthz", "/api/voice/health"]:
            return await self.app(scope, receive, send)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]

        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )

        self.requests[client_ip].append(now)
        return await self.app(scope, receive, send)
