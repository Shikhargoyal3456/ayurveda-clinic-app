from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, get_current_doctor, pop_flash
from app.config import settings
from app.database import get_db
from app.models import Doctor, Patient
from models.clinic_ops import PatientHealthPassport
from services.health_passport_service import ensure_health_passport
from shared.template_engine import render_template


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["health-passport"])


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _passport_payload(passport: PatientHealthPassport) -> dict[str, object]:
    return {
        "prakriti": passport.prakriti or {"vata": 33, "pitta": 33, "kapha": 34},
        "vikriti": passport.vikriti or {},
        "visitHistory": passport.visit_history or [],
        "prescriptions": passport.prescriptions or [],
        "ongoingMedications": passport.ongoing_medications or [],
        "allergies": passport.allergies or [],
        "contraindications": passport.contraindications or [],
        "followUpHistory": passport.follow_up_history or [],
        "dietaryRestrictions": passport.dietary_restrictions or [],
        "lifestyleNotes": passport.lifestyle_notes or "",
    }


@router.get("/patient/{patient_id}/health-passport")
def health_passport_page(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    passport = ensure_health_passport(db, patient, doctor.id)
    return render_template(
        templates,
        request,
        "patients/health_passport.html",
        {
            "doctor": doctor,
            "patient": patient,
            "clinic_name": settings.clinic_name,
            "passport": _passport_payload(passport),
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.get("/patient/{patient_id}/health-card")
def health_card_page(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    passport = ensure_health_passport(db, patient, doctor.id)
    card_url = str(request.url)
    return render_template(
        templates,
        request,
        "patients/health_card.html",
        {
            "doctor": doctor,
            "patient": patient,
            "clinic_name": settings.clinic_name,
            "doctor_name": settings.doctor_name or doctor.full_name or doctor.username,
            "passport": _passport_payload(passport),
            "card_url": card_url,
            "qr_url": f"/patient/{patient.id}/health-card/qr",
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.get("/patient/{patient_id}/health-card/qr")
def health_card_qr_placeholder(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    link = str(request.base_url).rstrip("/") + f"/patient/{patient.id}/health-card"
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220">
      <rect width="220" height="220" fill="#ffffff"/>
      <rect x="12" y="12" width="196" height="196" rx="18" fill="#1B6CA8"/>
      <rect x="26" y="26" width="72" height="72" fill="#ffffff"/>
      <rect x="122" y="26" width="72" height="72" fill="#ffffff"/>
      <rect x="26" y="122" width="72" height="72" fill="#ffffff"/>
      <rect x="44" y="44" width="36" height="36" fill="#1B6CA8"/>
      <rect x="140" y="44" width="36" height="36" fill="#1B6CA8"/>
      <rect x="44" y="140" width="36" height="36" fill="#1B6CA8"/>
      <text x="110" y="132" font-size="16" text-anchor="middle" fill="#ffffff" font-family="Arial">Scan / Open</text>
      <text x="110" y="154" font-size="10" text-anchor="middle" fill="#dbeafe" font-family="Arial">{link}</text>
    </svg>
    """
    return Response(content=svg, media_type="image/svg+xml")
