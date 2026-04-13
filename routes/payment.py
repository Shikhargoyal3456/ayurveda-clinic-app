from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

try:
    import razorpay
except ImportError:  # pragma: no cover
    razorpay = None
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.analytics import track_event
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
        .limit(200)
        .all()
    )
    todays_total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.date == today, Payment.status == "paid")
        .scalar()
    )
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).order_by(Patient.name.asc()).limit(500).all()
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
    track_event("payment_recorded", doctor_id=doctor.id, patient_id=patient.id, status=payment.status)
    set_flash(request, "Payment recorded.", "success")
    return RedirectResponse(url="/payments/daily", status_code=303)


@router.post("/payments/razorpay/create-order")
async def create_razorpay_order(
    request: Request,
    patient_id: int = Form(...),
    amount: str = Form(...),
    payment_date: str = Form(""),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    try:
        parsed_amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        return JSONResponse({"error": "Invalid amount."}, status_code=400)
    if parsed_amount <= 0:
        return JSONResponse({"error": "Amount must be greater than zero."}, status_code=400)
    if razorpay is None:
        write_audit_event("razorpay_order_failed", request, patient_id=patient.id)
        return JSONResponse({"error": "Razorpay is temporarily unavailable."}, status_code=503)

    try:
        client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
        order = client.order.create({
            "amount": int(parsed_amount * 100),
            "currency": "INR",
            "receipt": f"pay_{patient.id}_{int(parsed_amount)}",
            "notes": {
                "patient_name": patient.name,
                "doctor_id": str(doctor.id),
            }
        })
    except Exception as exc:
        write_audit_event("razorpay_order_failed", request, patient_id=patient.id)
        return JSONResponse({"error": "Razorpay order creation failed. Please try again."}, status_code=502)

    try:
        parsed_date = datetime.strptime(payment_date, "%Y-%m-%d").date() if payment_date else date.today()
    except ValueError:
        parsed_date = date.today()

    payment = Payment(
        patient_id=patient.id,
        amount=parsed_amount,
        status="pending",
        date=parsed_date,
        razorpay_order_id=order["id"],
        payment_method="razorpay",
    )
    db.add(payment)
    commit_with_retry(db)
    write_audit_event(
        "razorpay_order_created", request,
        payment_id=payment.id, patient_id=patient.id,
        order_id=order["id"]
    )
    return JSONResponse({
        "order_id": order["id"],
        "amount": int(parsed_amount * 100),
        "currency": "INR",
        "key_id": settings.razorpay_key_id,
        "patient_name": patient.name,
        "payment_db_id": payment.id,
    })


@router.post("/payments/razorpay/verify")
async def verify_razorpay_payment(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    razorpay_order_id = body.get("razorpay_order_id", "")
    razorpay_payment_id = body.get("razorpay_payment_id", "")
    razorpay_signature = body.get("razorpay_signature", "")
    payment_db_id = body.get("payment_db_id")

    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, razorpay_signature):
        return JSONResponse({"error": "Payment verification failed."}, status_code=400)

    payment = db.query(Payment).filter(
        Payment.id == payment_db_id,
        Payment.razorpay_order_id == razorpay_order_id,
    ).first()

    if payment is None:
        return JSONResponse({"error": "Payment record not found."}, status_code=404)

    payment.status = "paid"
    commit_with_retry(db)
    write_audit_event(
        "razorpay_payment_verified", request,
        payment_id=payment.id, razorpay_payment_id=razorpay_payment_id
    )
    track_event("payment_recorded", doctor_id=doctor.id, patient_id=payment.patient_id, status="paid")
    return JSONResponse({"success": True, "payment_id": payment.id})


@router.post("/payments/razorpay/failed")
async def razorpay_payment_failed(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    payment_db_id = body.get("payment_db_id")
    if payment_db_id:
        payment = db.query(Payment).filter(Payment.id == payment_db_id).first()
        if payment:
            payment.status = "failed"
            commit_with_retry(db)
            write_audit_event(
                "razorpay_payment_failed", request,
                payment_id=payment.id
            )
    return JSONResponse({"received": True})
