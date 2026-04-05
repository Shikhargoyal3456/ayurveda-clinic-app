from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import aggregate_daily_statistics, track_event
from app.auth import get_current_doctor
from app.config import settings
from app.health import build_health_report
from app.models import Appointment, CaseSheet, Doctor, Patient
from app.security import active_session_count, active_sessions_snapshot
from app.database import get_db


router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _require_admin(doctor: Doctor) -> Doctor:
    if settings.admin_usernames and doctor.username not in settings.admin_usernames:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return doctor


def _database_size() -> int:
    if not settings.database_url.startswith("sqlite:///"):
        return 0
    raw_path = settings.database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = settings.base_dir / path
    return path.stat().st_size if path.exists() else 0


def _metrics(db: Session) -> dict[str, object]:
    totals = {
        "patients": db.query(func.count(Patient.id)).scalar() or 0,
        "appointments": db.query(func.count(Appointment.id)).scalar() or 0,
        "case_sheets": db.query(func.count(CaseSheet.id)).scalar() or 0,
        "doctors": db.query(func.count(Doctor.id)).scalar() or 0,
    }
    return {
        "totals": totals,
        "database_size_bytes": _database_size(),
        "active_sessions": active_session_count(),
        "active_session_details": active_sessions_snapshot(),
        "analytics": aggregate_daily_statistics(),
        "health": build_health_report(),
    }


@router.get("/admin")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    payload = _metrics(db)
    track_event("admin_dashboard_viewed", doctor_id=doctor.id)
    return templates.TemplateResponse(request, "admin_dashboard.html", {"doctor": doctor, "metrics": payload})


@router.get("/api/admin/metrics")
def admin_metrics(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    payload = _metrics(db)
    track_event("admin_metrics_requested", doctor_id=doctor.id)
    return JSONResponse(payload)
