from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, get_current_doctor, pop_flash
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Doctor, Patient
from app.models.clinic_ops import PatientHealthPassport
from shared.template_engine import render_template


router = APIRouter(tags=["patient-health-passport"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _get_passport(db: Session, patient: Patient, doctor_id: int) -> PatientHealthPassport:
    passport = db.query(PatientHealthPassport).filter(PatientHealthPassport.patient_id == patient.id).first()
    if passport is None:
        passport = PatientHealthPassport(patient_id=patient.id, doctor_id=doctor_id)
        db.add(passport)
        commit_with_retry(db)
        db.refresh(passport)
    return passport


def _payload(passport: PatientHealthPassport) -> dict[str, object]:
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


def _patient(db: Session, doctor_id: int, patient_id: int) -> Patient:
    return db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()


@router.get("/patient/{patient_id}/health-passport")
def health_passport_page(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient(db, doctor.id, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    passport = _get_passport(db, patient, doctor.id)
    return render_template(templates, request, "patients/health_passport.html", {"doctor": doctor, "patient": patient, "clinic_name": settings.clinic_name, "passport": _payload(passport), "flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)})


@router.get("/patient/{patient_id}/health-card")
def health_card_page(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient(db, doctor.id, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    passport = _get_passport(db, patient, doctor.id)
    return render_template(templates, request, "patients/health_card.html", {"doctor": doctor, "patient": patient, "clinic_name": settings.clinic_name, "doctor_name": getattr(settings, "doctor_name", "") or doctor.full_name or doctor.username, "passport": _payload(passport), "card_url": str(request.url), "qr_url": f"/patient/{patient.id}/health-card/qr", "flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)})


@router.get("/patient/{patient_id}/health-card/qr")
def health_card_qr(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient(db, doctor.id, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    link = str(request.base_url).rstrip("/") + f"/patient/{patient.id}/health-card"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220"><rect width="220" height="220" fill="#fff"/><rect x="12" y="12" width="196" height="196" rx="18" fill="#1B6CA8"/><text x="110" y="105" font-size="16" text-anchor="middle" fill="#fff" font-family="Arial">Kash AI Health Card</text><text x="110" y="132" font-size="11" text-anchor="middle" fill="#dbeafe" font-family="Arial">Patient {patient.id}</text></svg>'
    return Response(svg, media_type="image/svg+xml", headers={"X-Health-Card-URL": link})
