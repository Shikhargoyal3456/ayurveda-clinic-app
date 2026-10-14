from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
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
from app.models import Doctor
from app.security import invalidate_current_session
from models.ai_log import AILog

router = APIRouter(prefix="/v2", tags=["v2"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/login")
def v2_login_page(request: Request):
    return RedirectResponse(url="/auth/login", status_code=303)


@router.post("/login")
def v2_login_submit():
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/dashboard")
def v2_dashboard_alias():
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/patients")
def v2_patients_alias():
    return RedirectResponse(url="/patients", status_code=303)


@router.get("/patients/{patient_id}")
def v2_patient_alias(patient_id: int):
    return RedirectResponse(url=f"/emr/patient/{patient_id}", status_code=303)


@router.get("/logout")
def v2_logout_alias():
    return RedirectResponse(url="/auth/logout", status_code=303)


def _require_admin(request: Request, db: Session = Depends(get_db)) -> Doctor:
    doctor = get_current_doctor(request, db)
    if doctor is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    username_lower = (doctor.username or "").lower()
    if not (username_lower.startswith("admin") or username_lower in getattr(settings, "admin_usernames", [])):
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
