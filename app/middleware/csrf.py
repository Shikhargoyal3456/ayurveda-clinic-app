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
            token = request.headers.get("X-CSRF-Token")
            if not token:
                try:
                    form = await request.form()
                    token = form.get("csrf_token")
                except Exception:
                    pass

            if not token:
                raise HTTPException(status_code=403, detail="CSRF token missing")

            session_token = request.cookies.get("csrf_token")
            if not session_token or not secrets.compare_digest(token, session_token):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")

        return await call_next(request)
