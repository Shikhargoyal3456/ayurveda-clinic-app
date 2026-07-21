from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import (
    ensure_csrf_token,
    get_current_doctor,
    hash_password,
    initialize_login_session,
    needs_password_rehash,
    normalized_username,
    register_login_failure,
    verify_csrf,
    verify_password,
)
from app.config import settings
from app.database import commit_with_retry, get_db
from app.main import app
from app.models import Doctor
from app.security import invalidate_current_session
from models.ai_log import AILog
from shared.template_engine import Jinja2Templates


router = APIRouter(prefix="/v2", tags=["v2"])
templates = Jinja2Templates(directory=str(settings.base_dir / "templates_v2"))

# V2 Authentication Routes

@router.get("/login")
def v2_login_page(request: Request):
    return RedirectResponse(url="/new/login", status_code=303)


# NOTE: The authentication logic in this function is an intentional duplication of
# the legacy doctor login flow found in `routers.auth.login`. It should be kept
# in sync with any security-related changes made there. This is a temporary
# necessity because the original logic is embedded within a route handler and is
# not available as a reusable service function. This implementation *does* reuse
# the core security primitives like `verify_password`, `register_login_failure`
# (for account locking), and `initialize_login_session` from `app.auth`.
@router.post("/login")
def v2_login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
):
    normalized = normalized_username(identifier.strip())
    doctor = db.query(Doctor).filter(Doctor.username == normalized).first()

    if doctor and doctor.locked_until and doctor.locked_until > datetime.now(timezone.utc):
        error_msg = "Account temporarily locked after repeated failures."
        return RedirectResponse(url=f"/v2/login?error={error_msg}", status_code=303)

    if doctor is None or not verify_password(password, doctor.password_hash):
        # The actual error message is flashed in the session, but since we are
        # not using flash messages in v2 yet, we pass a generic error.
        # register_login_failure handles backoff and locking.
        error_msg = register_login_failure(doctor, normalized, request, db if doctor is not None else None)
        write_audit_event("v2_login_failed", request, username=normalized)
        return RedirectResponse(url=f"/v2/login?error=Invalid username or password.", status_code=303)

    if needs_password_rehash(doctor.password_hash):
        doctor.password_hash = hash_password(password)
        commit_with_retry(db)

    initialize_login_session(request, doctor, db)
    write_audit_event("v2_login_success", request, doctor_id=doctor.id, username=doctor.username)
    track_event("v2_doctor_login", doctor_id=doctor.id, username=doctor.username)

    return RedirectResponse(url="/v2/dashboard", status_code=303)


@router.get("/logout")
def v2_logout(request: Request):
    write_audit_event("v2_logout", request)
    invalidate_current_session(request)
    return RedirectResponse(url="/v2/login", status_code=303)


# V2 Application Routes

@router.get("/dashboard")
def v2_dashboard(request: Request, doctor: Doctor = Depends(get_current_doctor)):
    return RedirectResponse(url="/new/doctor", status_code=303)

@router.get("/patients")
async def v2_patient_registry(
    request: Request,
    q: str = Query(""),
    doctor: Doctor = Depends(get_current_doctor),
):
    patients = []
    error = None
    try:
        # Use an async client to make an internal API call.
        # This reuses the existing API logic without duplicating the query.
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # Pass along the session cookie to the internal request for authentication
            cookies = {"session": request.cookies.get("session")}
            response = await client.get("/api/patients/search", params={"q": q}, cookies=cookies)
            response.raise_for_status()
            data = response.json()
            # The actual patient data is nested in the 'results' key
            patients = data.get("results", [])
    except Exception as e:
        error = f"Failed to load patients: {e}"

    return templates.TemplateResponse(
        "patients/registry.html",
        {
            "request": request,
            "doctor": doctor,
            "patients": patients,
            "search_query": q,
            "error": error,
        },
    )


# V2 Admin Routes

def _require_admin(doctor: Doctor = Depends(get_current_doctor)):
    # A simplified admin check for this new dashboard.
    # A robust implementation would use the portal user roles.
    allowed_admins = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    if not doctor or (doctor.username or "").strip().lower() not in allowed_admins and not (not settings.is_production and doctor.id == 1):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return doctor


@router.get("/admin/accuracy-dashboard")
def ai_accuracy_dashboard(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(_require_admin)):
    logs = db.query(AILog).order_by(AILog.created_at.desc()).limit(50).all()

    total_calls = db.query(AILog).count()
    feedback_counts = db.query(AILog.feedback_status, func.count(AILog.id)).group_by(AILog.feedback_status).all()
    stats = {
        "total_calls": total_calls,
        "pending": next((count for status, count in feedback_counts if status == 'pending'), 0),
        "accepted": next((count for status, count in feedback_counts if status == 'accepted'), 0),
        "rejected": next((count for status, count in feedback_counts if status == 'rejected'), 0),
    }

    return templates.TemplateResponse(
        "admin/accuracy_dashboard.html",
        {
            "request": request,
            "logs": logs,
            "stats": stats,
            "csrf_token": request.session.get("csrf_token"),
        },
    )


@router.post("/api/ai-log/{log_id}/feedback")
def save_ai_log_feedback(
    log_id: int,
    request: Request,
    status: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    _doctor: Doctor = Depends(_require_admin),
    __csrf: None = Depends(verify_csrf),
):
    log_entry = db.get(AILog, log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found.")

    log_entry.feedback_status = status
    log_entry.feedback_notes = notes.strip()
    commit_with_retry(db)

    return RedirectResponse(url="/v2/admin/accuracy-dashboard", status_code=303)
