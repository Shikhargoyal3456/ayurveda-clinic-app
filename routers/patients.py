from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Appointment, CaseSheet, Doctor, Patient
from models.payment import Payment
from models.prescription import Prescription


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["patients"])


@router.get("/")
def root(request: Request):
    if request.session.get("doctor_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "landing.html", {})


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
    write_audit_event("patient_created", request, patient_id=patient.id, patient_name=patient.name)
    set_flash(request, f"Patient {patient.name} added successfully.", "success")
    return RedirectResponse(url="/dashboard", status_code=303)
