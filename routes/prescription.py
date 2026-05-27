from __future__ import annotations

from datetime import datetime, timedelta
import textwrap

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from itsdangerous import URLSafeTimedSerializer

try:
    import fitz
except Exception:
    fitz = None

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Doctor, Patient
from app.prescription_library import (
    build_prescription_share_message,
    get_medicine_catalog,
    get_prescription_templates,
)
from models.prescription import Prescription
from services.communication import send_patient_message
from services.email_service import EmailService
from services.pure_ai_core import pure_ai
from services.sms_service import SMSService
from shared.template_engine import render_template
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["prescriptions"])
PRESCRIPTION_ORDER_SALT = "prescription-order"
email_service = EmailService()
sms_service = SMSService()


def _prescription_order_token(prescription_id: int) -> str:
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=PRESCRIPTION_ORDER_SALT)
    return serializer.dumps({"prescription_id": prescription_id})


def _prescription_order_url(request: Request, prescription_id: int) -> str:
    return str(
        request.url_for(
            "prescription_medicine_order_page",
            prescription_token=_prescription_order_token(prescription_id),
        )
    )


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _build_medicines(
    names: list[str],
    dosages: list[str],
    frequencies: list[str],
    durations: list[str],
) -> list[dict[str, str]]:
    medicines: list[dict[str, str]] = []
    for index, raw_name in enumerate(names):
        name = raw_name.strip()
        dosage = dosages[index].strip() if index < len(dosages) else ""
        frequency = frequencies[index].strip() if index < len(frequencies) else ""
        duration = durations[index].strip() if index < len(durations) else ""
        if not name:
            continue
        medicines.append({"name": name, "dosage": dosage, "frequency": frequency, "duration": duration})
    return medicines


def _last_prescription_for_patient(db: Session, doctor_id: int, patient_id: int) -> Prescription | None:
    return (
        db.query(Prescription)
        .filter(Prescription.doctor_id == doctor_id, Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .first()
    )


def _recent_prescriptions_for_patient(db: Session, doctor_id: int, patient_id: int) -> list[Prescription]:
    return (
        db.query(Prescription)
        .filter(Prescription.doctor_id == doctor_id, Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(3)
        .all()
    )


def _prescription_for_doctor(db: Session, doctor_id: int, prescription_id: int) -> Prescription:
    prescription = (
        db.query(Prescription)
        .join(Patient, Patient.id == Prescription.patient_id)
        .filter(Prescription.id == prescription_id, Prescription.doctor_id == doctor_id, Patient.doctor_id == doctor_id)
        .first()
    )
    if prescription is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return prescription


def _build_prescription_pdf_bytes(prescription: Prescription, doctor: Doctor) -> bytes:
    if fitz is None:
        raise RuntimeError("Prescription PDF download is temporarily unavailable.")
    document = fitz.open()
    page = document.new_page()
    y_position = 48

    def write_line(text: str, font_size: int = 11, gap: int = 18, bold: bool = False) -> None:
        nonlocal y_position, page
        font_name = "helvetica-bold" if bold else "helvetica"
        for line in textwrap.wrap(text, width=88) or [""]:
            page.insert_text((48, y_position), line, fontsize=font_size, fontname=font_name)
            y_position += gap

    write_line(settings.clinic_name, font_size=18, gap=24, bold=True)
    write_line(f"Doctor: {doctor.full_name or doctor.username}")
    write_line(f"Prescription ID: #{prescription.id}")
    write_line(f"Date: {(prescription.created_at or datetime.now()).strftime('%d %b %Y, %I:%M %p')}")
    write_line("")
    write_line(f"Patient: {prescription.patient.name}", bold=True)
    write_line(f"Phone: {prescription.patient.phone or 'Not available'}")
    write_line(f"Diagnosis: {prescription.diagnosis}")
    write_line(f"Follow-up: {str(prescription.follow_up_days) + ' days' if prescription.follow_up_days else 'Not specified'}")
    write_line("")
    write_line("Medicines", bold=True)
    for medicine in prescription.medicines or []:
        name = str(medicine.get("name", "")).strip()
        dosage = str(medicine.get("dosage", "")).strip()
        frequency = str(medicine.get("frequency", "")).strip()
        details = ", ".join(part for part in [dosage, frequency] if part)
        write_line(f"- {name}" + (f" ({details})" if details else ""))
    write_line("")
    write_line("Advice", bold=True)
    write_line(prescription.advice or "No additional advice recorded.")

    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def _doctor_display_name(doctor: Doctor) -> str:
    return (doctor.full_name or doctor.username or "Doctor").strip()


def _prescription_duration_label(prescription: Prescription) -> str:
    if prescription.follow_up_days:
        return f"{prescription.follow_up_days} days"
    return "As prescribed"


def _prescription_followup_label(prescription: Prescription) -> str:
    try:
        payload = pure_ai.schedule_followup_sync(
            {
                "condition": prescription.diagnosis or "Follow-up review",
                "severity": "Medium",
                "phase": "Post prescription",
            }
        )
        recommended_date = str(payload.get("recommended_date") or "").strip()
        if recommended_date:
            return datetime.fromisoformat(recommended_date).strftime("%d %b %Y")
    except Exception:
        pass
    if not prescription.follow_up_days:
        return "As advised by your doctor"
    base_date = prescription.created_at or datetime.now()
    return (base_date + timedelta(days=prescription.follow_up_days)).strftime("%d %b %Y")


def _send_prescription_email_only(
    prescription: Prescription,
    doctor: Doctor,
) -> dict[str, object]:
    if not prescription.patient.email:
        return {"success": False, "skipped": True, "reason": "missing_email"}

    pdf_bytes = _build_prescription_pdf_bytes(prescription, doctor) if fitz is not None else None

    import asyncio

    return asyncio.run(
        email_service.send_prescription(
            to_email=prescription.patient.email,
            patient_name=prescription.patient.name,
            doctor_name=_doctor_display_name(doctor),
            diagnosis=prescription.diagnosis or "",
            medicines=prescription.medicines or [],
            doctor_notes=prescription.advice or "",
            followup_date=_prescription_followup_label(prescription),
            pdf_bytes=pdf_bytes,
            pdf_filename=f"prescription-{prescription.id}.pdf",
        )
    )


@router.get("/patients/{patient_id}/prescriptions/new")
def prescription_form(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    specialty = (doctor.specialty or "ayurveda").strip().lower()
    patient = (
        db.query(Patient)
        .options(joinedload(Patient.cases), joinedload(Patient.doctor))
        .filter(Patient.id == patient_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    last_prescription = _last_prescription_for_patient(db, doctor.id, patient.id)
    return render_template(templates, request,
        "prescriptions/form.html",
        {
            "patient": patient,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
            "prescription_templates": get_prescription_templates(),
            "medicine_catalog": get_medicine_catalog(specialty),
            "last_prescription": last_prescription,
            "recent_prescriptions": _recent_prescriptions_for_patient(db, doctor.id, patient.id),
            "clinic_name": settings.clinic_name,
            "current_datetime": datetime.now(),
        },
    )


@router.post("/prescriptions/create")
def create_prescription(
    request: Request,
    patient_id: int = Form(...),
    diagnosis: str = Form(..., min_length=2, max_length=255),
    advice: str = Form("", max_length=5000),
    follow_up_days: int | None = Form(default=None),
    medicine_name: list[str] = Form(default=[]),
    medicine_dosage: list[str] = Form(default=[]),
    medicine_frequency: list[str] = Form(default=[]),
    medicine_days: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    access = check_subscription_access(doctor, "prescription")
    if not access["allowed"]:
        return JSONResponse(build_paywall_response(doctor, "prescription"), status_code=403)
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    cleaned_diagnosis = diagnosis.strip()
    medicines = _build_medicines(medicine_name, medicine_dosage, medicine_frequency, medicine_days)
    if not cleaned_diagnosis:
        set_flash(request, "Diagnosis is required before generating a prescription.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/prescriptions/new", status_code=303)
    if not medicines:
        set_flash(request, "Add at least one medicine before generating the prescription.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/prescriptions/new", status_code=303)
    if follow_up_days is not None and (follow_up_days < 1 or follow_up_days > 365):
        set_flash(request, "Follow-up days must be between 1 and 365.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/prescriptions/new", status_code=303)

    prescription = Prescription(
        patient_id=patient.id,
        doctor_id=doctor.id,
        profile_name=patient.name,
        diagnosis=cleaned_diagnosis,
        medicines=medicines,
        advice=advice.strip(),
        follow_up_days=follow_up_days,
    )
    db.add(prescription)
    commit_with_retry(db)
    increment_usage(doctor, "prescription")

    send_patient_message(
        patient.phone,
        patient.email,
        f"Your prescription is ready. Order medicines here: {_prescription_order_url(request, prescription.id)}",
        subject="Your Kash AI prescription is ready",
    )
    write_audit_event(
        "prescription_created",
        request,
        prescription_id=prescription.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
    )
    set_flash(request, "Prescription generated successfully.", "success")
    return RedirectResponse(url=f"/prescriptions/{prescription.id}?created=1", status_code=303)


@router.get("/prescriptions/{prescription_id}")
def view_prescription(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    prescription = _prescription_for_doctor(db, doctor.id, prescription_id)

    return render_template(templates, request,
        "prescriptions/detail.html",
        {
            "prescription": prescription,
            "prescription_token": _prescription_order_token(prescription.id),
            "patient": prescription.patient,
            "doctor": doctor,
            "flash": pop_flash(request),
            "created": request.query_params.get("created") == "1",
            "csrf_token": ensure_csrf_token(request),
            "clinic_name": settings.clinic_name,
            "current_datetime": datetime.now(),
            "recommended_followup_date": (
                prescription.created_at + timedelta(days=prescription.follow_up_days)
                if prescription.created_at and prescription.follow_up_days
                else None
            ),
        },
    )


@router.get("/prescriptions/{prescription_id}/download")
def download_prescription_pdf(
    prescription_id: int,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    prescription = _prescription_for_doctor(db, doctor.id, prescription_id)
    if fitz is None:
        raise HTTPException(status_code=503, detail="Prescription download is temporarily unavailable. Please try again later.")
    pdf_bytes = _build_prescription_pdf_bytes(prescription, doctor)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="prescription-{prescription.id}.pdf"',
        },
    )


@router.post("/prescriptions/{prescription_id}/share")
def share_prescription(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    prescription = _prescription_for_doctor(db, doctor.id, prescription_id)

    share_message = build_prescription_share_message(
        patient_name=prescription.patient.name,
        diagnosis=prescription.diagnosis,
        medicines=prescription.medicines or [],
        advice=prescription.advice or "",
    )
    share_message = f"{share_message}\n\nOrder your medicines here: {_prescription_order_url(request, prescription.id)}"
    email_result = _send_prescription_email_only(prescription, doctor)

    patient_result = send_patient_message(
        prescription.patient.phone,
        prescription.patient.email,
        share_message,
        subject="Your Kash AI prescription",
    )

    if prescription.patient.phone:
        import asyncio

        sms_service_result = asyncio.run(
            sms_service.send_prescription_alert(
                prescription.patient.phone,
                prescription.patient.name,
                _doctor_display_name(doctor),
            )
        )
        if sms_service_result.get("success"):
            patient_result["sms"] = True
            patient_result["whatsapp"] = True

    write_audit_event(
        "prescription_shared_email_sms",
        request,
        prescription_id=prescription.id,
        patient_id=prescription.patient_id,
        doctor_id=doctor.id,
        email_sent=bool(email_result.get("success")),
        sms_sent=bool(patient_result.get("sms")),
    )
    if email_result.get("success") or patient_result.get("sms"):
        set_flash(request, "Prescription sent to the patient by email and SMS.", "success")
    elif prescription.patient.email or prescription.patient.phone:
        set_flash(request, "Prescription saved, but delivery could not be completed right now.", "danger")
    else:
        set_flash(request, "Add patient email or phone to send this prescription.", "danger")
    return RedirectResponse(url=f"/prescriptions/{prescription.id}", status_code=303)


@router.post("/prescriptions/{prescription_id}/share/email")
def share_prescription_via_email(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    prescription = _prescription_for_doctor(db, doctor.id, prescription_id)
    email_result = _send_prescription_email_only(prescription, doctor)

    write_audit_event(
        "prescription_shared_email_only",
        request,
        prescription_id=prescription.id,
        patient_id=prescription.patient_id,
        doctor_id=doctor.id,
        email_sent=bool(email_result.get("success")),
    )

    if email_result.get("success"):
        set_flash(request, "Prescription sent to the patient's email.", "success")
    elif email_result.get("reason") == "missing_email":
        set_flash(request, "Add the patient's email address before sending via Gmail.", "danger")
    elif email_result.get("reason") == "smtp_not_configured":
        set_flash(request, "Gmail SMTP is not configured. Add SMTP or email credentials in .env.", "danger")
    else:
        set_flash(request, "Email could not be sent right now. Please try again.", "danger")

    return RedirectResponse(url=f"/prescriptions/{prescription.id}", status_code=303)
