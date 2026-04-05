from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Doctor, Patient
from models.payment import Payment


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["payments"])


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/payments/daily")
def daily_payments(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    today = date.today()
    payments = (
        db.query(Payment)
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.date == today)
        .order_by(Payment.id.desc())
        .all()
    )
    todays_total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.date == today, Payment.status == "paid")
        .scalar()
    )
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).order_by(Patient.name.asc()).all()
    return templates.TemplateResponse(
        request,
        "payments/daily.html",
        {
            "payments": payments,
            "patients": patients,
            "todays_total": float(todays_total or 0),
            "today": today,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/payments/add")
def add_payment(
    request: Request,
    patient_id: int = Form(...),
    amount: str = Form(...),
    payment_status: str = Form("unpaid"),
    payment_date: str = Form(""),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    try:
        parsed_amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        set_flash(request, "Payment amount must be a valid number.", "danger")
        return RedirectResponse(url="/payments/daily", status_code=303)
    if parsed_amount < 0:
        set_flash(request, "Payment amount cannot be negative.", "danger")
        return RedirectResponse(url="/payments/daily", status_code=303)

    try:
        parsed_date = datetime.strptime(payment_date, "%Y-%m-%d").date() if payment_date else date.today()
    except ValueError:
        set_flash(request, "Payment date must use the YYYY-MM-DD format.", "danger")
        return RedirectResponse(url="/payments/daily", status_code=303)

    normalized_status = "paid" if payment_status == "paid" else "unpaid"
    payment = Payment(
        patient_id=patient.id,
        amount=parsed_amount,
        status=normalized_status,
        date=parsed_date,
    )
    db.add(payment)
    commit_with_retry(db)
    write_audit_event("payment_added", request, payment_id=payment.id, patient_id=patient.id, status=payment.status)
    set_flash(request, "Payment recorded.", "success")
    return RedirectResponse(url="/payments/daily", status_code=303)

