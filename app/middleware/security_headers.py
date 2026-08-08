from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; connect-src 'self' https:; "
            "media-src 'self' https://d8j0ntlcm91z4.cloudfront.net; frame-src 'self' https:;",
        )
        if settings.is_production and request.headers.get("x-forwarded-proto", request.url.scheme) == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
