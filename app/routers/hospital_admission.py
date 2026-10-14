from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.auth import get_current_user
from app.models import Doctor, Hospital, HospitalAdmission, Patient


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hospital", tags=["hospital"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
ADMISSION_STATUSES = {"pending", "admitted", "discharged", "cancelled"}
TERMINAL_STATUSES = {"discharged", "cancelled"}


def _admission_payload(admission: HospitalAdmission) -> dict[str, object]:
    return {
        "id": admission.id,
        "patient_id": admission.patient_id,
        "doctor_id": admission.doctor_id,
        "hospital_id": admission.hospital_id,
        "admission_type": admission.admission_type,
        "diagnosis": admission.diagnosis,
        "reason": admission.reason_for_admission,
        "status": admission.status,
        "bed_number": admission.bed_number,
        "ward": admission.ward,
        "emergency": admission.emergency,
        "admission_requested_at": admission.admission_requested_at,
        "admitted_at": admission.admitted_at,
        "discharged_at": admission.discharged_at,
        "created_at": admission.created_at,
        "updated_at": admission.updated_at,
    }


def _whatsapp_url(phone: str, admission_id: int, hospital_name: str) -> str | None:
    digits = "".join(character for character in (phone or "") if character.isdigit())
    if not digits:
        return None
    message = f"Your hospital admission request #{admission_id} for {hospital_name} has been received. Status: pending."
    return f"https://wa.me/{digits}?text={quote(message)}"


def _require_clinician(
    user: dict[str, object] | None,
    db: Session,
) -> tuple[dict[str, object], int | None]:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to manage hospital admissions.")
    role = str(user.get("role") or "").strip().lower()
    if role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Only doctors and administrators can manage admissions.")
    doctor_id = None
    if user.get("source") == "legacy":
        try:
            doctor_id = int(user.get("id"))
        except (TypeError, ValueError):
            doctor_id = None
    elif role == "doctor" and user.get("email"):
        email = str(user["email"]).strip().lower()
        doctor = db.query(Doctor).filter(func.lower(Doctor.username) == email).first()
        if doctor is None and email.endswith("@kashai.com"):
            legacy_username = email.removesuffix("@kashai.com")
            doctor = db.query(Doctor).filter(func.lower(Doctor.username) == legacy_username).first()
        doctor_id = doctor.id if doctor is not None else None
    return user, doctor_id


def _authorize_admission(user: dict[str, object], doctor_id: int | None, admission: HospitalAdmission) -> None:
    if str(user.get("role") or "").strip().lower() != "admin" and (
        doctor_id is None or admission.doctor_id != doctor_id
    ):
        raise HTTPException(status_code=403, detail="You cannot access this admission.")


@router.get("/list", response_class=HTMLResponse)
async def hospital_list(request: Request, db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).order_by(Hospital.city, Hospital.name).all()
    return templates.TemplateResponse(
        "hospital/list.html",
        {"request": request, "hospitals": hospitals, "csrf_token": getattr(request.state, "csrf_token", "")},
    )


@router.get("/admission", response_class=HTMLResponse)
async def admission_form(request: Request, patient_id: int | None = None, db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).order_by(Hospital.city, Hospital.name).all()
    patient = db.get(Patient, patient_id) if patient_id is not None else None
    return templates.TemplateResponse(
        "hospital/admission.html",
        {"request": request, "hospitals": hospitals, "patient": patient, "csrf_token": getattr(request.state, "csrf_token", "")},
    )


@router.get("/api/hospitals")
async def get_hospitals(db: Session = Depends(get_db)):
    hospitals = db.query(Hospital).order_by(Hospital.city, Hospital.name).all()
    return {
        "success": True,
        "hospitals": [
            {
                "id": hospital.id,
                "name": hospital.name,
                "address": hospital.address,
                "city": hospital.city,
                "phone": hospital.phone,
                "email": hospital.email,
                "bed_capacity": hospital.bed_capacity,
                "available_beds": hospital.available_beds,
                "emergency_available": hospital.emergency_available,
            }
            for hospital in hospitals
        ],
    }


@router.post("/api/admission/request")
async def submit_admission(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, object] | None = Depends(get_current_user),
):
    current_user, current_doctor_id = _require_clinician(current_user, db)
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="A JSON request body is required.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="A JSON object is required.")

    try:
        patient_id = int(data.get("patient_id"))
        hospital_id = int(data.get("hospital_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Valid patient_id and hospital_id are required.") from exc
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Reason for admission is required.")
    if len(reason) > 4000:
        raise HTTPException(status_code=422, detail="Reason for admission is too long.")

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    is_admin = str(current_user.get("role") or "").strip().lower() == "admin"
    if not is_admin and (current_doctor_id is None or patient.doctor_id != current_doctor_id):
        raise HTTPException(status_code=403, detail="You cannot create an admission for this patient.")
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="Hospital not found.")

    doctor_id = data.get("doctor_id")
    if not is_admin:
        doctor_id = current_doctor_id
    elif doctor_id not in (None, ""):
        try:
            doctor_id = int(doctor_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="doctor_id must be an integer.") from exc
        if db.get(Doctor, doctor_id) is None:
            raise HTTPException(status_code=404, detail="Doctor not found.")
    else:
        # Older hospital_admissions tables required doctor_id, so preserve that
        # constraint by associating an unassigned request with the patient's doctor.
        doctor_id = patient.doctor_id

    if data.get("emergency") and not hospital.emergency_available:
        raise HTTPException(status_code=409, detail="This hospital is not accepting emergency admissions.")

    requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    admission = HospitalAdmission(
        patient_id=patient_id,
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        admission_type=str(data.get("admission_type") or ("emergency" if data.get("emergency") else "planned"))[:50],
        reason_for_admission=reason,
        diagnosis=str(data.get("diagnosis") or "")[:4000],
        emergency=bool(data.get("emergency", False)),
        status="pending",
        admission_requested_at=requested_at,
        created_at=requested_at,
        updated_at=requested_at,
    )
    try:
        # Conditional UPDATE prevents concurrent requests from reserving the same last bed.
        reserved = db.execute(
            update(Hospital)
            .where(Hospital.id == hospital_id, Hospital.available_beds > 0)
            .values(available_beds=Hospital.available_beds - 1)
        )
        if reserved.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="No beds are currently available.")
        db.add(admission)
        db.commit()
        db.refresh(admission)
        db.refresh(hospital)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Hospital admission request failed")
        raise HTTPException(status_code=500, detail="Admission request could not be saved.") from exc

    return {
        "success": True,
        "message": "Admission request submitted.",
        "admission_id": admission.id,
        "status": admission.status,
        "remaining_beds": hospital.available_beds,
        "whatsapp_url": _whatsapp_url(patient.phone, admission.id, hospital.name),
    }


@router.get("/api/admission/{admission_id}")
async def get_admission_status(
    admission_id: int,
    db: Session = Depends(get_db),
    current_user: dict[str, object] | None = Depends(get_current_user),
):
    current_user, current_doctor_id = _require_clinician(current_user, db)
    admission = db.get(HospitalAdmission, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found.")
    _authorize_admission(current_user, current_doctor_id, admission)
    return {"success": True, "admission": _admission_payload(admission)}


@router.put("/api/admission/{admission_id}")
async def update_admission_status(
    admission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict[str, object] | None = Depends(get_current_user),
):
    current_user, current_doctor_id = _require_clinician(current_user, db)
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="A JSON request body is required.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="A JSON object is required.")
    new_status = str(data.get("status") or "").strip().lower()
    if new_status not in ADMISSION_STATUSES:
        raise HTTPException(status_code=422, detail="Status must be pending, admitted, discharged, or cancelled.")

    admission = db.get(HospitalAdmission, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found.")
    _authorize_admission(current_user, current_doctor_id, admission)
    previous_status = admission.status
    if new_status == previous_status:
        return {"success": True, "status": admission.status, "message": "Status is unchanged."}
    if previous_status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="A discharged or cancelled admission cannot be reopened.")
    if new_status == "pending":
        raise HTTPException(status_code=409, detail="An admission cannot return to pending.")

    hospital = db.get(Hospital, admission.hospital_id)
    if hospital is None:
        raise HTTPException(status_code=409, detail="The admission hospital no longer exists.")
    try:
        if new_status in TERMINAL_STATUSES:
            released = db.execute(
                update(Hospital)
                .where(Hospital.id == hospital.id, Hospital.available_beds < Hospital.bed_capacity)
                .values(available_beds=Hospital.available_beds + 1)
            )
            if released.rowcount != 1:
                db.rollback()
                raise HTTPException(status_code=409, detail="Bed availability is already at capacity.")
            admission.discharged_at = datetime.now(timezone.utc).replace(tzinfo=None) if new_status == "discharged" else None
        if new_status == "admitted":
            admission.admitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        admission.status = new_status
        db.commit()
        db.refresh(admission)
        db.refresh(hospital)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Hospital admission status update failed")
        raise HTTPException(status_code=500, detail="Admission status could not be updated.") from exc

    return {"success": True, "status": admission.status, "available_beds": hospital.available_beds}
