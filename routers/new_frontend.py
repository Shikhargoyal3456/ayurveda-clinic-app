from __future__ import annotations

from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.database import SessionLocal, get_db
from app.demo_seed import create_demo_data
from app.models import Appointment, CaseSheet, Doctor, Patient
from models.payment import Payment
from models.prescription import Prescription
from models.care_plan import PatientCarePlan
from models.user import UserRole
from models.user import PatientProfile
from app.portal_auth import dashboard_path_for_role, get_portal_user, ensure_legacy_doctor_for_portal_user, normalize_phone
from app.config import settings
from shared.template_engine import render_template
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from services.profile_service import active_profiles_for_user, resolve_active_profile, profile_avatar_for_relationship
from services.backup_service import BackupService
from models.audit_log import AuditLog

templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/new", tags=["new-frontend"])


def _current_user_or_redirect(request: Request, db: Session, login_url: str = "/auth/login"):
    user = get_portal_user(request, db)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": login_url})
    return user


def _role_guard(request: Request, db: Session, expected_role: str):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value != expected_role:
        raise HTTPException(status_code=303, headers={"Location": dashboard_path_for_role(role_value)})
    return user


def _doctor_dashboard_context(request: Request, db: Session, user) -> dict[str, object]:
    legacy_doctor = ensure_legacy_doctor_for_portal_user(db, user)
    if legacy_doctor is not None:
        demo_patients = db.query(Patient).filter(Patient.doctor_id == legacy_doctor.id).count()
        if demo_patients == 0:
            create_demo_data(db, legacy_doctor)
    patient_query = db.query(Patient)
    if legacy_doctor is not None:
        patient_query = patient_query.filter(Patient.doctor_id == legacy_doctor.id)
    else:
        patient_query = patient_query.filter(Patient.doctor_id == -1)
    patients = patient_query.order_by(Patient.created_at.desc(), Patient.id.desc()).all()
    today = __import__("datetime").date.today()
    appointments = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(Patient.doctor_id == legacy_doctor.id if legacy_doctor is not None else False)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
        if legacy_doctor is not None
        else []
    )
    today_appointments = [item for item in appointments if item.date == today]
    follow_ups = (
        db.query(CaseSheet)
        .join(Patient, Patient.id == CaseSheet.patient_id)
        .filter(Patient.doctor_id == legacy_doctor.id, CaseSheet.followup_date.isnot(None), CaseSheet.followup_date <= today)
        .order_by(CaseSheet.followup_date.asc(), CaseSheet.created_at.desc())
        .all()
        if legacy_doctor is not None
        else []
    )
    revenue = (
        db.query(Payment)
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == legacy_doctor.id, Payment.date == today)
        .all()
        if legacy_doctor is not None
        else []
    )
    return {
        "request": request,
        "user": user,
        "csrf_token": request.state.csrf_token,
        "now": __import__("datetime").datetime.now(),
        "doctor_name": user.full_name or "Doctor",
        "doctor": legacy_doctor,
        "patients": patients[:5],
        "today_appointments": today_appointments,
        "follow_ups": follow_ups,
        "revenue": revenue,
        "patient_count": len(patients),
        "appointment_count": len(appointments),
        "follow_up_count": len(follow_ups),
        "revenue_today": sum(float(item.amount or 0) for item in revenue),
        "ai_brief": (
            f"You have {len(today_appointments)} appointment(s) today and {len(follow_ups)} follow-up(s) due."
            if legacy_doctor is not None
            else "Your live clinic data will appear here after the first refresh."
        ),
        "nav_appointments_href": "/appointments",
        "visit_labels": [item.date.strftime("%d %b") for item in appointments[-30:]],
        "visit_data": [1 for _ in appointments[-30:]],
        "demographics_data": [
            sum(1 for item in patients if str(getattr(item, "gender", "")).lower() == "male"),
            sum(1 for item in patients if str(getattr(item, "gender", "")).lower() == "female"),
            sum(1 for item in patients if str(getattr(item, "gender", "")).lower() not in {"male", "female"}),
        ],
        "revenue_labels": [today.strftime("%b")],
        "revenue_data": [round(sum(float(item.amount or 0) for item in revenue), 2)],
        "diagnosis_labels": ["General"],
        "diagnosis_data": [len(patients)],
        "recent_activities": [
            {
                "time": item.created_at.strftime("%H:%M") if getattr(item, "created_at", None) else "",
                "text": f"Appointment with {getattr(item.patient, 'name', 'patient')}" if getattr(item, "patient", None) else "Recent activity",
                "status": "success",
                "status_label": "Done",
            }
            for item in appointments[:5]
        ],
        "total_patients": len(patients),
        "new_patients": len([item for item in patients if getattr(item, "created_at", None) and item.created_at.date() == today]),
        "today_appointments": len(today_appointments),
        "upcoming_appointments": max(0, len(appointments) - len(today_appointments)),
        "revenue_this_month": round(sum(float(item.amount or 0) for item in revenue), 2),
        "revenue_growth": 0,
        "avg_rating": 4.8,
        "total_reviews": len(patients),
        "ai_assisted_cases": len(appointments),
        "ai_success_rate": 95,
        "completion_rate": 100 if appointments else 0,
        "pending_cases": len(follow_ups),
    }


def _patient_dashboard_context_new(request: Request, db: Session, user) -> dict[str, object]:
    profiles = active_profiles_for_user(db, user.id)
    active_profile = resolve_active_profile(request, db, user)
    if active_profile is not None:
        request.session["active_profile_name"] = active_profile.profile_name
        request.session["active_profile_avatar"] = profile_avatar_for_relationship(active_profile.relationship, active_profile.profile_avatar)
        request.session["active_profile_relationship"] = active_profile.relationship
    patient = (
        db.query(Patient)
        .filter(
            or_(
                Patient.email == (user.email or ""),
                Patient.phone == normalize_phone(user.phone or ""),
                Patient.name == (user.full_name or ""),
            )
        )
        .order_by(Patient.created_at.desc(), Patient.id.desc())
        .first()
    )
    if patient is None:
        portal_profile = db.get(PatientProfile, user.id)
        if portal_profile is not None:
            patient = db.query(Patient).filter(Patient.email == (user.email or "")).order_by(Patient.created_at.desc(), Patient.id.desc()).first()
    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient.id)
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
        if patient is not None
        else []
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .all()
        if patient is not None
        else []
    )
    care_plans = (
        db.query(PatientCarePlan)
        .filter(PatientCarePlan.patient_id == patient.id)
        .order_by(PatientCarePlan.created_at.desc())
        .all()
        if patient is not None
        else []
    )
    upcoming_appointments = [item for item in appointments if item.date and item.date >= __import__("datetime").date.today()]
    health_score = 75
    if patient is not None:
        health_score = max(0, min(100, 65 + len(upcoming_appointments) * 3 + len(prescriptions) * 2 - len([item for item in appointments if str(item.status).lower() in {"cancelled", "missed"}]) * 4))
    return {
        "request": request,
        "user": user,
        "csrf_token": request.state.csrf_token,
        "profiles": profiles,
        "active_profile": active_profile,
        "patient": patient,
        "appointments": appointments,
        "upcoming_appointments": upcoming_appointments[:3],
        "prescriptions": prescriptions,
        "care_plans": care_plans,
        "health_score": health_score,
        "health_message": (
            f"You have {len(upcoming_appointments)} upcoming appointment(s) and {len(prescriptions)} prescription(s)."
            if patient is not None
            else "No linked patient record was found."
        ),
    }


@router.get("")
def landing(request: Request):
    db = SessionLocal()
    try:
        user = _current_user_or_redirect(request, db, login_url="/new")
    except Exception:
        user = None
    finally:
        db.close()
    context = {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")}
    if user is not None:
        context["user"] = user
    return render_template(templates, request, "new_landing.html", context)


@router.get("/")
def landing_slash(request: Request):
    return landing(request)


@router.get("/login")
def login(request: Request):
    return render_template(templates, request, "new_login.html", {"request": request, "csrf_token": request.state.csrf_token})


@router.get("/signup")
def signup(request: Request):
    return render_template(templates, request, "new_signup.html", {"request": request, "csrf_token": request.state.csrf_token})


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value == UserRole.doctor.value:
        context = _doctor_dashboard_context(request, db, user)
        return render_template(templates, request, "new_dashboard.html", context)
    if role_value == UserRole.patient.value:
        return RedirectResponse(url="/patient/dashboard", status_code=303)
    if role_value == UserRole.admin.value:
        return RedirectResponse(url="/new/admin", status_code=303)
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/doctor")
def doctor_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _role_guard(request, db, UserRole.doctor.value)
    context = _doctor_dashboard_context(request, db, user)
    return render_template(templates, request, "new_dashboard.html", context)


@router.get("/patient")
def patient_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _role_guard(request, db, UserRole.patient.value)
    context = _patient_dashboard_context_new(request, db, user)
    return render_template(templates, request, "new_patient_dashboard.html", context)


@router.get("/ai-doctor")
def ai_doctor(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    return render_template(templates, request, "new_ai_doctor.html", {"request": request, "user": user, "csrf_token": request.state.csrf_token})


@router.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value != UserRole.admin.value:
        return RedirectResponse(url="/new/doctor" if role_value == UserRole.doctor.value else "/patient/dashboard", status_code=303)
    backups = []
    audit_logs = []
    try:
        backups = BackupService().list_backups()[:10]
    except Exception:
        backups = []
    try:
        audit_logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all()
    except Exception:
        audit_logs = []
    return render_template(
        templates,
        request,
        "admin/complete_admin.html",
        {
            "request": request,
            "user": user,
            "csrf_token": request.state.csrf_token,
            "backups": backups,
            "audit_logs": audit_logs,
        },
    )


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    return render_template(templates, request, "new_settings.html", {"request": request, "user": user, "csrf_token": request.state.csrf_token})


@router.get("/terms")
def terms_page(request: Request):
    return render_template(templates, request, "terms.html", {"request": request})


@router.get("/privacy")
def privacy_page(request: Request):
    return render_template(templates, request, "privacy.html", {"request": request})


@router.get("/patients")
@router.get("/appointments")
@router.get("/prescriptions")
@router.get("/labs")
def section_redirect(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    path = request.url.path
    if role_value == UserRole.doctor.value:
        if path.endswith("/patients"):
            return RedirectResponse(url="/emr/patient-registry", status_code=303)
        if path.endswith("/appointments"):
            return RedirectResponse(url="/appointments", status_code=303)
        if path.endswith("/labs"):
            return RedirectResponse(url="/diagnostics/lab-booking", status_code=303)
        return RedirectResponse(url="/new/doctor", status_code=303)
    if role_value == UserRole.patient.value:
        if path.endswith("/appointments"):
            return RedirectResponse(url="/my-health", status_code=303)
        if path.endswith("/prescriptions"):
            return RedirectResponse(url="/my-health", status_code=303)
        if path.endswith("/labs"):
            return RedirectResponse(url="/diagnostics/lab-booking", status_code=303)
        return RedirectResponse(url="/patient/dashboard", status_code=303)
    return RedirectResponse(url="/new/admin", status_code=303)


@router.get("/patient/dashboard")
def patient_dashboard_alias(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/patient/dashboard", status_code=303)


@router.get("/patient/ai-assistant")
def patient_ai_assistant_alias(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    return render_template(
        templates,
        request,
        "patient/ai_assistant.html",
        {"request": request, "user": user, "csrf_token": request.state.csrf_token},
    )


@router.get("/patient/legacy")
def patient_legacy_alias(request: Request):
    return RedirectResponse(url="/patient/legacy-portal", status_code=303)


@router.get("/patient/legacy-portal")
def patient_legacy_portal(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    return render_template(
        templates,
        request,
        "patient/legacy_portal.html",
        {"request": request, "user": user, "csrf_token": request.state.csrf_token},
    )


@router.get("/patient/my-health")
def patient_my_health_alias(request: Request):
    return RedirectResponse(url="/patient/dashboard", status_code=303)


@router.get("/patient/appointments")
def patient_appointments_alias(request: Request):
    return RedirectResponse(url="/patient/dashboard", status_code=303)


@router.get("/patient/prescriptions")
def patient_prescriptions_alias(request: Request):
    return RedirectResponse(url="/patient/dashboard", status_code=303)


@router.get("/patients/add")
def add_patient_redirect(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value != UserRole.doctor.value:
        return RedirectResponse(url="/patient/dashboard", status_code=303)
    return RedirectResponse(url="/emr/patient-registration", status_code=303)


@router.get("/patients/{patient_id}/cases/new")
def new_case_redirect(patient_id: int, request: Request, db: Session = Depends(get_db)):
    _current_user_or_redirect(request, db)
    return RedirectResponse(url=f"/patients/{patient_id}/cases/new", status_code=303)


@router.get("/prescriptions/new")
def new_prescription_redirect(request: Request, db: Session = Depends(get_db)):
    user = _current_user_or_redirect(request, db)
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value == UserRole.doctor.value:
        return RedirectResponse(url="/new/doctor", status_code=303)
    return RedirectResponse(url="/my-health", status_code=303)


@router.get("/patient/{item_id}")
def patient_detail_redirect(item_id: int, request: Request, db: Session = Depends(get_db)):
    _current_user_or_redirect(request, db)
    return RedirectResponse(url=f"/emr/patient/{item_id}", status_code=303)


@router.get("/appointment/{item_id}")
def appointment_detail_redirect(item_id: int, request: Request, db: Session = Depends(get_db)):
    _current_user_or_redirect(request, db)
    return RedirectResponse(url="/appointments", status_code=303)


@router.get("/prescription/{item_id}")
def prescription_detail_redirect(item_id: int, request: Request, db: Session = Depends(get_db)):
    _current_user_or_redirect(request, db)
    return RedirectResponse(url="/prescriptions", status_code=303)
