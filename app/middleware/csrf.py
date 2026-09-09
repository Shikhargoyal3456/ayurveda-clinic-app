from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import secrets


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.excluded_paths = [
            "/auth/google/login",
            "/auth/google/callback",
            "/auth/login",
            "/auth/signup",
            "/healthz",
            "/static",
            "/shared-static",
            "/api/webhook",
            "/api/voice/transcribe",
            "/api/voice/health",
            "/api/voice/extract",
            "/api/consultation/save",
            "/api/tongue-analyze",
            "/api/ai-chat",
            "/api/generate-billing-codes",
            "/api/recommend-medicines",
            "/api/predict-churn",
            "/api/device/check",
            "/telemedicine/start",
        ]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)

        if path.startswith("/api/") and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            token = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken") or request.headers.get("x-csrf-token")
            session_token = None
            try:
                session_token = request.session.get("_csrf_token") or request.cookies.get("csrf_token")
            except Exception:
                pass
            if session_token and token and not secrets.compare_digest(token, session_token):
                from starlette.responses import JSONResponse
                return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})

        return await call_next(request)
