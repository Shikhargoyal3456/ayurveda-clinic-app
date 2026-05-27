from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Appointment, CaseSheet, Doctor, Patient
from shared.template_engine import render_template


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["appointments"])


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/patients/{patient_id}/appointments/new")
def schedule_page(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    return render_template(
        templates,
        request,
        "schedule.html",
        {
            "patient": patient,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/patients/{patient_id}/appointments")
def save_appointment(
    patient_id: int,
    request: Request,
    date_value: str = Form(..., alias="date"),
    time: str = Form(..., max_length=10),
    reason: str = Form("", max_length=255),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    try:
        appointment_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        set_flash(request, "Appointment date must use the YYYY-MM-DD format.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/appointments/new", status_code=303)

    appointment = Appointment(
        patient_id=patient.id,
        date=appointment_date,
        time=time,
        reason=reason.strip(),
    )
    db.add(appointment)
    commit_with_retry(db)
    write_audit_event("appointment_created", request, appointment_id=appointment.id, patient_id=patient.id)
    set_flash(request, "Appointment scheduled.", "success")
    return RedirectResponse(url="/appointments", status_code=303)


@router.get("/appointments")
def appointments_page(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    today = date.today()
    todays_appointments = (
        db.query(Appointment)
        .join(Patient)
        .options(joinedload(Appointment.patient))
        .filter(Patient.doctor_id == doctor.id, Appointment.date == today)
        .order_by(Appointment.time.asc())
        .limit(100)
        .all()
    )
    upcoming_appointments = (
        db.query(Appointment)
        .join(Patient)
        .options(joinedload(Appointment.patient))
        .filter(Patient.doctor_id == doctor.id, Appointment.date > today)
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .limit(25)
        .all()
    )
    total_appointments = (
        db.query(Appointment)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id)
        .count()
    )
    scheduled_today = sum(1 for item in todays_appointments if (item.status or "").lower() == "scheduled")
    return render_template(
        templates,
        request,
        "appointments.html",
        {
            "appointments": todays_appointments,
            "upcoming_appointments": upcoming_appointments,
            "total_appointments": total_appointments,
            "scheduled_today": scheduled_today,
            "flash": pop_flash(request),
        },
    )


@router.get("/followups")
def followups_page(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    today = date.today()
    due_cases = (
        db.query(CaseSheet)
        .join(Patient)
        .options(joinedload(CaseSheet.patient))
        .filter(Patient.doctor_id == doctor.id, CaseSheet.followup_date == today)
        .order_by(CaseSheet.followup_date.asc(), CaseSheet.created_at.desc())
        .limit(100)
        .all()
    )
    pending_cases = (
        db.query(CaseSheet)
        .join(Patient)
        .options(joinedload(CaseSheet.patient))
        .filter(Patient.doctor_id == doctor.id, CaseSheet.followup_date > today)
        .order_by(CaseSheet.followup_date.asc(), CaseSheet.created_at.desc())
        .limit(250)
        .all()
    )
    overdue_cases = (
        db.query(CaseSheet)
        .join(Patient)
        .options(joinedload(CaseSheet.patient))
        .filter(Patient.doctor_id == doctor.id, CaseSheet.followup_date < today)
        .order_by(CaseSheet.followup_date.asc(), CaseSheet.created_at.desc())
        .limit(250)
        .all()
    )
    return render_template(
        templates,
        request,
        "followups.html",
        {
            "cases": due_cases,
            "pending_cases": pending_cases,
            "overdue_cases": overdue_cases,
            "flash": pop_flash(request),
        },
    )
