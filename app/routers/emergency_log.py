from __future__ import annotations

import csv
import io
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_doctor
from app.config import settings
from app.database import get_db
from app.models import Doctor, Patient
from app.models.clinic_ops import EmergencyAlertLog


router = APIRouter(tags=["emergency-log"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _alerts(db: Session, doctor_id: int, start_date: date | None = None, end_date: date | None = None):
    query = db.query(EmergencyAlertLog).filter(EmergencyAlertLog.doctor_id == doctor_id)
    if start_date:
        query = query.filter(EmergencyAlertLog.created_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(EmergencyAlertLog.created_at < datetime.combine(end_date, time.max))
    return query.order_by(EmergencyAlertLog.created_at.desc(), EmergencyAlertLog.id.desc()).limit(5000).all()


@router.get("/emergency-log", response_class=HTMLResponse)
def emergency_log_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    rows = _alerts(db, doctor.id, start_date, end_date)
    items = []
    for row in rows[:500]:
        patient = db.get(Patient, row.patient_id) if row.patient_id else None
        items.append({"date": row.created_at, "patient_name": patient.name if patient else "Unknown patient", "keyword": row.triggering_keyword, "action_taken": row.action_taken})
    return templates.TemplateResponse(
        "emergency/log.html",
        {
            "request": request,
            "doctor": doctor,
            "clinic_name": settings.clinic_name,
            "flash": None,
            "start_date": start_date.isoformat() if start_date else "",
            "end_date": end_date.isoformat() if end_date else "",
            "items": items,
        },
    )


@router.get("/emergency-log/export")
def export_emergency_log(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Patient", "Keyword", "Severity", "Action"])
    for row in _alerts(db, doctor.id):
        patient = db.get(Patient, row.patient_id) if row.patient_id else None
        writer.writerow([row.created_at.isoformat() if row.created_at else "", patient.name if patient else "Unknown patient", row.triggering_keyword, row.severity, row.action_taken])
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=emergency-log.csv"})
