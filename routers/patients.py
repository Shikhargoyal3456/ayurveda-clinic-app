from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_event
from app.analytics import track_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.portal_auth import dashboard_path_for_role, get_portal_user
from app.models import Appointment, CaseSheet, Doctor, Patient
from apps.patient.routes import patient_dashboard_context
from models.medicine import MedicineOrder
from models.outcome import Outcome
from models.payment import Payment
from models.prescription import Prescription
from services.superapp_service import get_dashboard_payload
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)
from routers.pharmacy import _is_repeat_order, _load_order_items, _order_again_token, _order_source
from services.profile_service import active_profiles_for_user, profile_avatar_for_relationship, resolve_active_profile


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["patients"])


def _iso(value):
    return value.isoformat() if value else None


def get_patient_insights(db: Session, patient_id: int) -> dict[str, object]:
    try:
        patient = db.get(Patient, patient_id)
        if patient is None or not patient.phone:
            return {
                "total_orders": 0,
                "last_order_date": None,
                "repeat_count": 0,
                "most_common_medicines": [],
            }
        orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.patient_phone == patient.phone)
            .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
            .all()
        )
        medicine_counter: Counter[str] = Counter()
        repeat_count = 0
        for order in orders:
            if _is_repeat_order(order):
                repeat_count += 1
            for item in _load_order_items(order):
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if name:
                        medicine_counter[name] += int(item.get("qty", 1) or 1)
        return {
            "total_orders": len(orders),
            "last_order_date": _iso(orders[0].created_at) if orders else None,
            "repeat_count": repeat_count,
            "most_common_medicines": [
                {"name": name, "count": count}
                for name, count in medicine_counter.most_common(3)
            ],
        }
    except Exception as exc:
        __import__("logging").getLogger(__name__).exception("Patient insights failed for patient_id=%s: %s", patient_id, exc)
        return {
            "total_orders": 0,
            "last_order_date": None,
            "repeat_count": 0,
            "most_common_medicines": [],
        }


@router.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    if request.session.get("doctor_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        role_value = getattr(portal_user.role, "value", str(portal_user.role))
        if role_value == "patient":
            profiles = active_profiles_for_user(db, portal_user.id)
            if not profiles:
                return RedirectResponse(url="/profiles/add", status_code=303)
            if len(profiles) > 1 and not request.session.get("active_profile_id"):
                return RedirectResponse(url="/profiles/select", status_code=303)
            active_profile = resolve_active_profile(request, db, portal_user)
            if active_profile is not None:
                request.session["active_profile_name"] = active_profile.profile_name
                request.session["active_profile_avatar"] = profile_avatar_for_relationship(active_profile.relationship, active_profile.profile_avatar)
                request.session["active_profile_relationship"] = active_profile.relationship
            return templates.TemplateResponse(request, "patient_home.html", patient_dashboard_context(request, portal_user))
        return RedirectResponse(url=dashboard_path_for_role(role_value), status_code=303)
    return templates.TemplateResponse(request, "patient_home.html", patient_dashboard_context(request))


@router.get("/my-health")
def my_health(request: Request, db: Session = Depends(get_db)):
    portal_user = get_portal_user(request, db)
    if portal_user is not None and getattr(portal_user.role, "value", str(portal_user.role)) == "patient":
        profiles = active_profiles_for_user(db, portal_user.id)
        if not profiles:
            return RedirectResponse(url="/profiles/add", status_code=303)
        if len(profiles) > 1 and not request.session.get("active_profile_id"):
            return RedirectResponse(url="/profiles/select", status_code=303)
    payload = get_dashboard_payload()
    subscriptions = payload.get("subscriptions", [])
    active_medicines = []
    for item in subscriptions[:5]:
        days_left = int(item.get("days_left", 0) or 0)
        tone = "yellow" if days_left <= 3 else "green"
        badge = "Refill soon" if days_left <= 3 else "On track"
        refill_text = "today" if days_left <= 0 else f"in {days_left} days"
        active_medicines.append(
            {
                "name": item.get("medicine_name", "Medicine"),
                "refill_text": refill_text,
                "tone": tone,
                "badge": badge,
            }
        )
    return templates.TemplateResponse(
        request,
        "patient/simple_health.html",
        {
            "request": request,
            "simple_nav": "health",
            "page_hint": "Your medicines and refill reminders",
            "health_score": payload.get("health_score", 85),
            "health_message": payload.get("health_message", "Your medicines and reminders are on track."),
            "active_medicines": active_medicines,
            "recent_consults": 2,
            "active_profile_name": request.session.get("active_profile_name", "Myself"),
        },
    )


@router.get("/orders")
def my_orders(request: Request, db: Session = Depends(get_db)):
    portal_user = get_portal_user(request, db)
    if portal_user is not None and getattr(portal_user.role, "value", str(portal_user.role)) == "patient":
        profiles = active_profiles_for_user(db, portal_user.id)
        if not profiles:
            return RedirectResponse(url="/profiles/add", status_code=303)
        if len(profiles) > 1 and not request.session.get("active_profile_id"):
            return RedirectResponse(url="/profiles/select", status_code=303)
    return templates.TemplateResponse(
        request,
        "orders/tracking.html",
        {
            "request": request,
            "simple_nav": "orders",
            "page_hint": "See where your medicine is",
            "simple_mode": True,
            "order": {"id": "", "timeline": []},
            "location": {"eta": ""},
            "active_profile_name": request.session.get("active_profile_name", "Myself"),
        },
    )


@router.get("/pricing")
def pricing_page(request: Request):
    return templates.TemplateResponse(request, "pricing.html", {})


@router.get("/investors")
def investor_page(request: Request):
    return templates.TemplateResponse(request, "investors.html", {})


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    allowed_admins = {item.strip().lower() for item in settings.admin_usernames if item.strip()}
    if (doctor.username or "").strip().lower() in allowed_admins:
        return RedirectResponse(url="/admin", status_code=303)
    today = date.today()
    current_datetime = datetime.now()
    appointment_count_sq = (
        db.query(func.count(Appointment.id))
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Appointment.date == today)
        .scalar_subquery()
    )
    patient_count_sq = (
        db.query(func.count(Patient.id))
        .filter(Patient.doctor_id == doctor.id, func.date(Patient.created_at) == today.isoformat())
        .scalar_subquery()
    )
    earnings_sq = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.date == today, Payment.status == "paid")
        .scalar_subquery()
    )
    pending_payments_sq = (
        db.query(func.count(Payment.id))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.status == "unpaid")
        .scalar_subquery()
    )
    followups_due_sq = (
        db.query(func.count(CaseSheet.id))
        .join(Patient, Patient.id == CaseSheet.patient_id)
        .filter(Patient.doctor_id == doctor.id, CaseSheet.followup_date <= today)
        .scalar_subquery()
    )
    dashboard_summary = (
        db.query(
            appointment_count_sq.label("todays_appointments"),
            patient_count_sq.label("todays_patients"),
            earnings_sq.label("todays_earnings"),
            pending_payments_sq.label("pending_payments"),
            followups_due_sq.label("followups_due"),
        )
        .one()
    )
    patients = (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor.id)
        .order_by(Patient.created_at.desc())
        .limit(500)
        .all()
    )
    total_patients = db.query(func.count(Patient.id)).filter(Patient.doctor_id == doctor.id).scalar() or 0
    upcoming_appointments = (
        db.query(Appointment)
        .join(Patient)
        .options(joinedload(Appointment.patient))
        .filter(Patient.doctor_id == doctor.id, Appointment.date == today)
        .order_by(Appointment.time.asc())
        .limit(5)
        .all()
    )
    due_followups = (
        db.query(CaseSheet)
        .join(Patient)
        .options(joinedload(CaseSheet.patient))
        .filter(Patient.doctor_id == doctor.id, CaseSheet.followup_date <= today)
        .order_by(CaseSheet.followup_date.asc(), CaseSheet.created_at.desc())
        .limit(5)
        .all()
    )
    total_cases = (
        db.query(func.count(CaseSheet.id))
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id)
        .scalar()
        or 0
    )
    returning_patients = (
        db.query(func.count(Patient.id))
        .filter(
            Patient.doctor_id == doctor.id,
            db.query(func.count(CaseSheet.id))
            .filter(CaseSheet.patient_id == Patient.id)
            .correlate(Patient)
            .scalar_subquery()
            > 1,
        )
        .scalar()
        or 0
    )
    latest_prescriptions = (
        db.query(Prescription)
        .join(Patient, Patient.id == Prescription.patient_id)
        .filter(Patient.doctor_id == doctor.id)
        .order_by(Prescription.created_at.desc())
        .limit(4)
        .all()
    )
    followup_prescriptions = (
        db.query(Prescription)
        .join(Patient, Patient.id == Prescription.patient_id)
        .options(joinedload(Prescription.patient))
        .filter(
            Patient.doctor_id == doctor.id,
            Prescription.follow_up_days.isnot(None),
        )
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(5)
        .all()
    )
    outstanding_payments = (
        db.query(Payment)
        .join(Patient, Patient.id == Payment.patient_id)
        .options(joinedload(Payment.patient))
        .filter(Patient.doctor_id == doctor.id, Payment.status == "unpaid")
        .order_by(Payment.date.desc(), Payment.id.desc())
        .limit(5)
        .all()
    )
    demo_mode_active = (
        db.query(func.count(Patient.id))
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"demo-clinic-{doctor.id}-%"))
        .scalar()
        or 0
    ) > 0
    next_visit_recommendations = [
        {
            "patient_name": prescription.patient.name,
            "diagnosis": prescription.diagnosis,
            "recommended_date": (
                prescription.created_at.date() + timedelta(days=prescription.follow_up_days)
                if prescription.created_at and prescription.follow_up_days
                else None
            ),
        }
        for prescription in followup_prescriptions
        if prescription.follow_up_days
    ]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "doctor": doctor,
            "clinic_name": settings.clinic_name,
            "current_datetime": current_datetime,
            "patients": patients,
            "total_patients": total_patients,
            "total_cases": total_cases,
            "todays_appointments": int(dashboard_summary.todays_appointments or 0),
            "todays_patients": int(dashboard_summary.todays_patients or 0),
            "todays_earnings": float(dashboard_summary.todays_earnings or 0),
            "pending_payments": int(dashboard_summary.pending_payments or 0),
            "followups_due": int(dashboard_summary.followups_due or 0),
            "returning_patients": returning_patients,
            "upcoming_appointments": upcoming_appointments,
            "due_followups": due_followups,
            "latest_prescriptions": latest_prescriptions,
            "outstanding_payments": outstanding_payments,
            "next_visit_recommendations": next_visit_recommendations,
            "demo_mode_active": demo_mode_active,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.get("/demo")
def demo_page(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "doctor": doctor,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.get("/patient/{patient_id}/timeline")
def patient_timeline(
    patient_id: int,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = db.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="Patient not found")

    cases = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient.id)
        .order_by(CaseSheet.created_at.desc())
        .all()
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .all()
    )
    medicine_orders = []
    if patient.phone:
        medicine_orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.patient_phone == patient.phone)
            .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
            .all()
        )
    payments = (
        db.query(Payment)
        .filter(Payment.patient_id == patient.id)
        .order_by(Payment.date.desc(), Payment.id.desc())
        .all()
    )
    outcomes = (
        db.query(Outcome)
        .filter(Outcome.patient_id == patient.id)
        .order_by(Outcome.date.desc(), Outcome.id.desc())
        .all()
    )

    return JSONResponse(
        {
            "success": True,
            "message": "Patient timeline loaded.",
            "data": {
                "patient": {
                    "id": patient.id,
                    "name": patient.name,
                    "phone": patient.phone,
                    "created_at": _iso(patient.created_at),
                },
                "insights": get_patient_insights(db, patient.id),
                "cases": [
                    {
                        "id": case.id,
                        "diagnosis": case.diagnosis,
                        "symptoms": case.symptoms,
                        "followup_date": _iso(case.followup_date),
                        "created_at": _iso(case.created_at),
                    }
                    for case in cases
                ],
                "prescriptions": [
                    {
                        "id": prescription.id,
                        "diagnosis": prescription.diagnosis,
                        "medicines": prescription.medicines,
                        "follow_up_days": prescription.follow_up_days,
                        "created_at": _iso(prescription.created_at),
                    }
                    for prescription in prescriptions
                ],
                "medicine_orders": [
                    {
                        "id": order.id,
                        "status": order.status,
                        "payment_status": order.payment_status,
                        "paid_at": _iso(order.paid_at),
                        "total_amount": order.total_amount,
                        "created_at": _iso(order.created_at),
                        "order_again_url": f"/pharmacy/order-again/{_order_again_token(order.id)}",
                        "source": _order_source(order),
                        "is_repeat_order": _is_repeat_order(order),
                    }
                    for order in medicine_orders
                ],
                "payments": [
                    {
                        "id": payment.id,
                        "amount": float(payment.amount or 0),
                        "status": payment.status,
                        "date": _iso(payment.date),
                        "payment_method": payment.payment_method,
                    }
                    for payment in payments
                ],
                "outcomes": [
                    {
                        "id": outcome.id,
                        "case_id": outcome.case_id,
                        "improvement_status": outcome.improvement_status,
                        "symptom_score": outcome.symptom_score,
                        "notes": outcome.notes,
                        "date": _iso(outcome.date),
                    }
                    for outcome in outcomes
                ],
            },
        }
    )


@router.post("/demo/create-workspace")
def create_demo_workspace(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    demo_email = f"demo-{doctor.id}@ayurvedaos.local"
    existing_patient = (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email == demo_email)
        .first()
    )
    if existing_patient is not None:
        set_flash(request, f"Demo workspace already exists for {existing_patient.name}.", "info")
        return RedirectResponse(url=f"/patients/{existing_patient.id}/cases", status_code=303)

    patient = Patient(
        doctor_id=doctor.id,
        name="Demo Patient",
        age=34,
        gender="Female",
        phone="9999999999",
        email=demo_email,
        address="Bengaluru",
    )
    db.add(patient)
    db.flush()

    case = CaseSheet(
        patient_id=patient.id,
        prakriti="Pitta-Vata",
        diagnosis="Amlapitta with agnimandya",
        symptoms=(
            "Burning sensation after meals, sour belching, irregular appetite, headache, disturbed sleep, "
            "stress-related digestive discomfort."
        ),
        notes="Pilot demo case showing intake, AI assistance, and follow-up workflow for a chronic patient.",
        followup_date=date.today() + timedelta(days=7),
        followup_notes="Review digestion, sleep, and adherence to ahara-vihara plan.",
    )
    db.add(case)

    appointment = Appointment(
        patient_id=patient.id,
        date=date.today(),
        time="11:30",
        reason="Digestive care follow-up demo consult",
        status="scheduled",
    )
    db.add(appointment)
    try:
        commit_with_retry(db)
    except IntegrityError:
        db.rollback()
        existing_patient = (
            db.query(Patient)
            .filter(Patient.doctor_id == doctor.id, Patient.email == demo_email)
            .first()
        )
        if existing_patient is not None:
            set_flash(request, f"Demo workspace already exists for {existing_patient.name}.", "info")
            return RedirectResponse(url=f"/patients/{existing_patient.id}/cases", status_code=303)
        raise

    write_audit_event("demo_workspace_created", request, doctor_id=doctor.id, patient_id=patient.id, case_id=case.id)
    set_flash(request, f"Demo workspace ready for {patient.name}.", "success")
    return RedirectResponse(url=f"/patients/{patient.id}/cases", status_code=303)


@router.post("/patients")
def create_patient(
    request: Request,
    name: str = Form(..., min_length=2, max_length=160),
    age: int = Form(...),
    gender: str = Form(..., max_length=30),
    phone: str = Form("", max_length=40),
    email: str = Form("", max_length=120),
    address: str = Form("", max_length=255),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    access = check_subscription_access(doctor, "patients")
    if not access["allowed"]:
        return JSONResponse(build_paywall_response(doctor, "patients"), status_code=403)
    patient = Patient(
        doctor_id=doctor.id,
        name=name.strip(),
        age=age,
        gender=gender.strip(),
        phone=phone.strip(),
        email=email.strip(),
        address=address.strip(),
    )
    db.add(patient)
    try:
        commit_with_retry(db)
    except IntegrityError:
        db.rollback()
        if email.strip():
            set_flash(request, "A patient with that email already exists in your clinic.", "danger")
        else:
            set_flash(request, "Patient could not be saved because of a data conflict.", "danger")
        return RedirectResponse(url="/dashboard", status_code=303)
    increment_usage(doctor, "patients")
    write_audit_event("patient_created", request, patient_id=patient.id, patient_name=patient.name)
    track_event("patient_created", doctor_id=doctor.id, patient_id=patient.id)
    set_flash(request, f"Patient {patient.name} added successfully.", "success")
    return RedirectResponse(url="/dashboard", status_code=303)
