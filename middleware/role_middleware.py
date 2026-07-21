from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse


from app.audit import write_audit_event


logger = logging.getLogger(__name__)


class RoleGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        session = request.scope.get("session") or {}
        role = str(session.get("portal_user_role") or "").strip()
        if path.startswith("/doctor") and role == "patient":
            write_audit_event("authorization_failed", request, path=path, role=role, reason="patient_blocked_from_doctor")
            logger.warning("authorization_failed path=%s role=%s", path, role)
            return RedirectResponse(url="/patient", status_code=303)
        if path.startswith("/patient") and role == "doctor":
            write_audit_event("authorization_failed", request, path=path, role=role, reason="doctor_blocked_from_patient")
            logger.warning("authorization_failed path=%s role=%s", path, role)
            return RedirectResponse(url="/doctor/dashboard", status_code=303)
        return await call_next(request)
