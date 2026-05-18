from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Doctor, Patient
from app.portal_auth import get_portal_user
from services.pure_ai_core import add_disclaimer, pure_ai


router = APIRouter(prefix="/api/pure-ai", tags=["Pure AI"])


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    return get_portal_user(request, db)


def _appointment_or_404(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


def _doctor_schedule_for_next_14_days(db: Session, doctor_id: int, skip_appointment_id: int | None = None) -> list[dict[str, Any]]:
    rows = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(
            Patient.doctor_id == doctor_id,
            Appointment.date >= date.today(),
            Appointment.date <= date.today() + timedelta(days=14),
        )
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
    )
    schedule: list[dict[str, Any]] = []
    for row in rows:
        if skip_appointment_id and row.id == skip_appointment_id:
            continue
        schedule.append(
            {
                "appointment_id": row.id,
                "date": row.date.isoformat() if row.date else None,
                "time": row.time,
                "status": row.status,
            }
        )
    return schedule


@router.post("/medicine-info")
async def pure_medicine_info(
    medicine_name: str = Query(..., min_length=1),
    patient_context: dict[str, Any] | None = Body(default=None),
):
    try:
        result = await pure_ai.get_medicine_info(medicine_name, patient_context)
        return add_disclaimer(
            {
                "success": True,
                "source": "ai",
                "confidence": result.get("confidence", 85),
                "confidence_factors": result.get("confidence_factors", {}),
                "requires_doctor_review": result.get("requires_doctor_review", False),
                "data": result,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI unavailable: {exc}") from exc


@router.post("/prescription")
async def pure_prescription(
    patient_data: dict[str, Any] = Body(...),
    doctor_notes: str | None = Query(default=None),
):
    try:
        result = await pure_ai.generate_personalized_prescription(patient_data, doctor_notes)
        return add_disclaimer(
            {
                "success": True,
                "source": "ai",
                "confidence": result.get("confidence", 85),
                "confidence_factors": result.get("confidence_factors", {}),
                "requires_doctor_review": result.get("requires_doctor_review", False),
                "prescription": result,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI unavailable: {exc}") from exc


@router.post("/schedule-followup")
async def pure_followup(
    patient_data: dict[str, Any] = Body(...),
    treatment_response: str | None = Query(default=None),
):
    try:
        result = await pure_ai.schedule_followup(patient_data, treatment_response)
        return add_disclaimer(
            {
                "success": True,
                "source": "ai",
                "confidence": result.get("confidence", 85),
                "confidence_factors": result.get("confidence_factors", {}),
                "requires_doctor_review": result.get("requires_doctor_review", False),
                "followup": result,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI unavailable: {exc}") from exc


@router.post("/reschedule-appointment/{appointment_id}")
async def pure_reschedule(
    appointment_id: int,
    patient_message: str = Body(..., embed=True),
    request: Request = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    appointment = _appointment_or_404(db, appointment_id)
    patient = db.get(Patient, appointment.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    doctor = db.get(Doctor, patient.doctor_id)
    current_appointment = {
        "id": appointment.id,
        "date": appointment.date.isoformat() if appointment.date else None,
        "time": appointment.time,
        "doctor_id": patient.doctor_id,
        "doctor_name": (doctor.full_name or doctor.username) if doctor else "Doctor",
        "patient_name": patient.name,
        "requested_by_user_id": getattr(user, "id", None),
        "request_path": request.url.path if request else "",
    }
    doctor_schedule = _doctor_schedule_for_next_14_days(db, patient.doctor_id, skip_appointment_id=appointment.id)
    try:
        result = await pure_ai.reschedule_appointment_ai(current_appointment, patient_message, doctor_schedule)
        return add_disclaimer(
            {
                "success": True,
                "source": "ai",
                "confidence": result.get("confidence", 85),
                "confidence_factors": result.get("confidence_factors", {}),
                "requires_doctor_review": result.get("requires_doctor_review", False),
                "reschedule": result,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI unavailable: {exc}") from exc
