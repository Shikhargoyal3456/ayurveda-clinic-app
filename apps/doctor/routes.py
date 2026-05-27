from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.portal_auth import (
    doctor_dashboard_path,
    ensure_legacy_doctor_for_portal_user,
    normalize_doctor_type,
    require_portal_roles,
    user_public_context,
)
from core.navigation import get_navigation_for_doctor, get_quick_actions_for_doctor
from core.dashboards import doctor_dashboard_context
from models.user import DoctorProfile
from services.emr_service import get_doctor_dashboard_data
from shared.template_engine import templates
from shared.template_engine import render_template


router = APIRouter(tags=["doctor-portal"])


def _doctor_dashboard_context(user, db: Session, request: Request) -> tuple[dict, str]:
    legacy_doctor = ensure_legacy_doctor_for_portal_user(db, user)
    doctor_profile = db.get(DoctorProfile, getattr(user, "id", None))
    doctor_type = normalize_doctor_type(
        getattr(doctor_profile, "doctor_type", None),
        getattr(doctor_profile, "specialization", None) or getattr(legacy_doctor, "specialty", None),
    )
    context = doctor_dashboard_context(
        doctor_id=getattr(legacy_doctor, "id", None),
        doctor_user_id=getattr(user, "id", None),
    )
    context.update(
        {
            "request": request,
            "active_page": "dashboard",
            "doctor_type": doctor_type,
            "doctor_dashboard_href": doctor_dashboard_path(
                getattr(doctor_profile, "doctor_type", None),
                getattr(doctor_profile, "specialization", None),
            ),
            "portal_navigation": get_navigation_for_doctor(doctor_type),
            "quick_actions": get_quick_actions_for_doctor(doctor_type),
            **user_public_context(user),
        }
    )
    raw_patients = context.get("patients", []) or []
    context["recent_patients"] = [
        {
            "id": patient.get("id"),
            "name": patient.get("name") or "Unknown patient",
            "age": patient.get("age"),
            "last_visit": (
                "Today"
                if getattr(patient.get("created_at"), "date", None) and patient.get("created_at").date() == date.today()
                else (
                    "Yesterday"
                    if getattr(patient.get("created_at"), "date", None) and patient.get("created_at").date() == (date.today() - timedelta(days=1))
                    else (
                        f"{(date.today() - patient.get('created_at').date()).days} days ago"
                        if getattr(patient.get("created_at"), "date", None) and (date.today() - patient.get("created_at").date()).days <= 6
                        else (
                            patient.get("created_at").strftime("%d %b %Y")
                            if getattr(patient.get("created_at"), "strftime", None)
                            else "Recently added"
                        )
                    )
                )
            ),
        }
        for patient in raw_patients[:5]
    ]
    emr_snapshot = get_doctor_dashboard_data(db, legacy_doctor) if legacy_doctor else {}
    hour = datetime.now().hour
    context["time_of_day"] = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    context["doctor_name"] = (
        getattr(user, "full_name", None)
        or context.get("doctor", {}).get("name")
        or context.get("user_name")
        or "Doctor"
    )
    context["pending_patients_count"] = int(context.get("waiting_count") or len(context.get("waiting_patients", []) or []))
    context["today_appointments_count"] = int(context.get("today_appointments") or 0)
    context["pending_prescriptions_count"] = int(context.get("pending_prescriptions") or 0)
    context["pending_lab_reports"] = len(emr_snapshot.get("pending_labs", []) or [])
    context["ai_dashboard_doctor_id"] = getattr(legacy_doctor, "id", None) or context.get("doctor", {}).get("id")
    return context, doctor_type


@router.get("/doctor/dashboard")
@router.get("/portal/doctor")
def dashboard(request: Request, user=Depends(require_portal_roles("doctor")), db: Session = Depends(get_db)):
    context, _ = _doctor_dashboard_context(user, db, request)
    return render_template(templates, request, "portals/doctor/dashboard.html", context)


@router.get("/doctor/{doctor_type}/dashboard")
def doctor_dashboard_variant(
    doctor_type: str,
    request: Request,
    user=Depends(require_portal_roles("doctor")),
    db: Session = Depends(get_db),
):
    context, resolved_type = _doctor_dashboard_context(user, db, request)
    normalized = normalize_doctor_type(doctor_type, resolved_type)
    context["doctor_type"] = normalized
    template_name = f"doctor/{normalized}/dashboard.html"
    return render_template(templates, request, template_name, context)
