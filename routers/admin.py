from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from models.care_plan import PatientCarePlan
from models.payment import Payment
from models.subscription import ClinicSubscription


router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _require_admin(doctor: Doctor) -> Doctor:
    allowed_admins = settings.admin_usernames or ["admin@ayurveda.com"]
    if doctor.username not in allowed_admins:
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


@router.get("/api/admin/saas-stats")
def saas_stats(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_doctors = db.query(func.count(Doctor.id)).scalar() or 0
    new_doctors_24h = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_24h
    ).scalar() or 0
    new_doctors_7d = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_7d
    ).scalar() or 0
    new_doctors_30d = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_30d
    ).scalar() or 0

    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    new_patients_24h = db.query(func.count(Patient.id)).filter(
        Patient.created_at >= last_24h
    ).scalar() or 0

    total_cases = db.query(func.count(CaseSheet.id)).scalar() or 0
    total_appointments = db.query(func.count(Appointment.id)).scalar() or 0

    total_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).scalar() or 0
    active_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.status == "active").scalar() or 0
    trial_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.status == "trial").scalar() or 0
    basic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.plan == "basic").scalar() or 0
    premium_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.plan == "premium").scalar() or 0

    total_care_plans = db.query(
        func.count(PatientCarePlan.id)
    ).scalar() or 0
    active_care_plans = db.query(
        func.count(PatientCarePlan.id)
    ).filter(PatientCarePlan.status == "active").scalar() or 0

    today = now.date()
    revenue_today = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Payment.status == "paid", Payment.date == today)
        .scalar() or 0
    )
    revenue_7d = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(
            Payment.status == "paid",
            Payment.date >= last_7d.date()
        )
        .scalar() or 0
    )
    revenue_30d = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(
            Payment.status == "paid",
            Payment.date >= last_30d.date()
        )
        .scalar() or 0
    )
    revenue_alltime = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Payment.status == "paid")
        .scalar() or 0
    )

    daily_signups = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = db.query(func.count(Doctor.id)).filter(
            func.date(Doctor.created_at) == day
        ).scalar() or 0
        daily_signups.append({"date": str(day), "count": count})

    track_event("saas_stats_viewed", doctor_id=doctor.id)
    return JSONResponse({
        "doctors": {
            "total": total_doctors,
            "new_24h": new_doctors_24h,
            "new_7d": new_doctors_7d,
            "new_30d": new_doctors_30d,
            "daily_signups": daily_signups,
        },
        "patients": {
            "total": total_patients,
            "new_24h": new_patients_24h,
        },
        "usage": {
            "total_cases": total_cases,
            "total_appointments": total_appointments,
        },
        "subscriptions": {
            "total": total_clinic_subs,
            "active": active_clinic_subs,
            "trial": trial_clinic_subs,
            "basic": basic_subs,
            "premium": premium_subs,
        },
        "care_plans": {
            "total": total_care_plans,
            "active": active_care_plans,
        },
        "revenue": {
            "today": revenue_today,
            "last_7d": revenue_7d,
            "last_30d": revenue_30d,
            "all_time": revenue_alltime,
        },
    })


@router.post("/api/admin/seed-demo-data")
def seed_demo_data(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    from models.subscription import ClinicSubscription
    from models.care_plan import PatientCarePlan
    from datetime import datetime, timedelta

    doctors = db.query(Doctor).limit(3).all()
    patients = db.query(Patient).limit(3).all()

    for i, d in enumerate(doctors):
        plans = ["free", "basic", "premium"]
        statuses = ["trial", "active", "active"]
        sub = ClinicSubscription(
            doctor_id=d.id,
            plan=plans[i % 3],
            status=statuses[i % 3],
            started_at=datetime.utcnow() - timedelta(days=30 - i * 5),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(sub)

    for i, p in enumerate(patients):
        cp = PatientCarePlan(
            patient_id=p.id,
            plan_name=["Basic Detox", "Panchakarma", "Rasayana"][i % 3],
            status=["active", "active", "completed"][i % 3],
            started_at=datetime.utcnow() - timedelta(days=15),
            expires_at=datetime.utcnow() + timedelta(days=45),
        )
        db.add(cp)

    db.commit()
    return JSONResponse({"seeded": True})
