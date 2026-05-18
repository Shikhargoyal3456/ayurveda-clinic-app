from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, get_current_doctor, pop_flash
from app.database import commit_with_retry, get_db
from app.models import Doctor, Patient
from app.config import settings
from models.emr import EMRConsultation, EMRPrescription, EMRPatientProfile
from routers.emr import _base_context, _patient_for_doctor, _profile_for_patient
from services.ambient_emr import AmbientEMRService
from services.emr_service import ensure_emr_profile, serialize_consultation, serialize_prescription, write_emr_audit_log


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["ambient-emr"])


active_sessions: dict[str, dict[str, Any]] = {}


def _doctor_patients(db: Session, doctor: Doctor) -> list[Patient]:
    return (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor.id)
        .order_by(Patient.created_at.desc())
        .limit(100)
        .all()
    )


def _ambient_context(
    request: Request,
    doctor: Doctor,
    db: Session,
    *,
    patient: Patient | None = None,
    profile: EMRPatientProfile | None = None,
) -> dict[str, Any]:
    context = _base_context(
        request,
        doctor,
        "ambient_scribe",
        {
            "patients": _doctor_patients(db, doctor),
            "selected_patient": patient,
            "selected_profile": profile,
            "csrf_token": ensure_csrf_token(request),
            "flash": pop_flash(request),
        },
    )
    return context


def _consultation_system_for_doctor(doctor: Doctor) -> str:
    specialty = (doctor.specialty or "ayurveda").strip().lower()
    if specialty in {"modern_medicine", "dental", "physiotherapy"}:
        return "modern"
    if specialty == "ayurveda":
        return "ayurveda"
    return "integrated"


def _profile_field_list(profile: EMRPatientProfile, key: str) -> list[str]:
    values = profile.medical_history.get(key, []) if isinstance(profile.medical_history, dict) else []
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    return []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    return []


def _prescription_items(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue
                items.append(
                    {
                        "name": name,
                        "dosage": str(entry.get("dosage") or "As directed").strip(),
                        "frequency": str(entry.get("frequency") or entry.get("instructions") or "As directed").strip(),
                        "duration": str(entry.get("duration") or "As directed").strip(),
                    }
                )
            else:
                text = str(entry or "").strip()
                if text:
                    items.append({"name": text, "dosage": "As directed", "frequency": "As directed", "duration": "As directed"})
    elif isinstance(value, str):
        for line in value.splitlines():
            text = line.strip()
            if not text:
                continue
            items.append({"name": text, "dosage": "As directed", "frequency": "As directed", "duration": "As directed"})
    return items[:6]


@router.get("/emr/ambient-scribe")
def ambient_scribe_page(
    request: Request,
    patient_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = None
    profile = None
    if patient_id is not None:
        patient = _patient_for_doctor(db, doctor.id, patient_id)
        profile = _profile_for_patient(db, patient)
    return templates.TemplateResponse(request, "emr/ambient_scribe.html", _ambient_context(request, doctor, db, patient=patient, profile=profile))


@router.post("/api/ambient-emr/session/start")
async def ambient_start_session(
    payload: dict[str, Any] = Body(default={}),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient_id = int(payload.get("patient_id") or 0) or None
    patient_context: dict[str, Any] = {}
    if patient_id is not None:
        patient = _patient_for_doctor(db, doctor.id, patient_id)
        profile = _profile_for_patient(db, patient)
        patient_context = {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "medical_history": _profile_field_list(profile, "past_conditions"),
            "allergies": list(profile.allergies or []),
        }

    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "doctor_id": doctor.id,
        "patient_id": patient_id,
        "service": AmbientEMRService(patient_context=patient_context),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"success": True, "session_id": session_id, "patient_id": patient_id}


@router.post("/api/ambient-emr/process-segment")
async def ambient_process_segment(
    session_id: str = Form(...),
    speaker: str = Form("auto"),
    transcript_text: str = Form(""),
    audio: UploadFile | None = File(default=None),
    doctor: Doctor = Depends(get_current_doctor),
):
    session = active_sessions.get(session_id)
    if session is None or session.get("doctor_id") != doctor.id:
        raise HTTPException(status_code=404, detail="Ambient EMR session not found")

    service: AmbientEMRService = session["service"]
    result = await service.process_conversation_segment(audio.file if audio is not None else None, transcript_text=transcript_text, speaker=speaker)
    return JSONResponse(result)


@router.post("/api/ambient-emr/session/{session_id}/finalize")
async def ambient_finalize_session(session_id: str, doctor: Doctor = Depends(get_current_doctor)):
    session = active_sessions.get(session_id)
    if session is None or session.get("doctor_id") != doctor.id:
        raise HTTPException(status_code=404, detail="Ambient EMR session not found")
    service: AmbientEMRService = session["service"]
    await service.extract_emr_from_conversation()
    return {"success": True, "emr_data": service.get_emr_json(), "patient_id": session.get("patient_id")}


@router.post("/api/ambient-emr/save")
async def ambient_save_emr(
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    session_id = str(payload.get("session_id", "")).strip()
    session = active_sessions.get(session_id)
    if session is None or session.get("doctor_id") != doctor.id:
        raise HTTPException(status_code=404, detail="Ambient EMR session not found")

    patient_id = int(payload.get("patient_id") or session.get("patient_id") or 0)
    if not patient_id:
        raise HTTPException(status_code=422, detail="Select a patient before saving ambient EMR.")

    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = ensure_emr_profile(db, patient)
    service: AmbientEMRService = session["service"]
    extracted = service.get_emr_json()
    overrides = payload.get("emr_data", {}) if isinstance(payload.get("emr_data"), dict) else {}
    merged = {
        **extracted,
        **{key: value for key, value in overrides.items() if not (value is None or value == "")},
    }
    merged["medications"] = _string_list(merged.get("medications"))
    merged["allergies"] = _string_list(merged.get("allergies"))
    merged["prescription"] = _prescription_items(merged.get("prescription"))

    system_type = str(payload.get("system_type") or _consultation_system_for_doctor(doctor))
    consultation = EMRConsultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        system_type=system_type,
        status="completed",
        title=str(payload.get("title") or "Ambient AI Scribe Consultation"),
        chief_complaint=str(merged.get("chief_complaint", "")),
        history_of_present_illness=str(merged.get("history_present_illness", "")),
        notes_json={
            "ambient_transcript": extracted.get("conversation_history", []),
            "past_medical_history": str(merged.get("past_medical_history", "")),
            "examination_findings": str(merged.get("examination_findings", "")),
            "medications": list(merged.get("medications", [])),
            "allergies": list(merged.get("allergies", [])),
        },
        diagnosis_json=[{"label": str(merged.get("diagnosis", ""))}] if str(merged.get("diagnosis", "")).strip() else [],
        treatment_plan=str(merged.get("treatment_plan", "")),
    )
    db.add(consultation)
    db.flush()

    existing_history = list((profile.medical_history or {}).get("past_conditions", [])) if isinstance(profile.medical_history, dict) else []
    merged_history = [item for item in existing_history if str(item).strip()]
    new_history = [item for item in str(merged.get("past_medical_history", "")).split(";") if item.strip()]
    for item in new_history:
        if item.strip() not in merged_history:
            merged_history.append(item.strip())
    profile.medical_history = {
        **(profile.medical_history or {}),
        "past_conditions": merged_history,
        "medications": list(merged.get("medications", [])),
    }
    if merged.get("allergies"):
        profile.allergies = [{"name": item} for item in merged.get("allergies", [])]

    prescription_items = list(merged.get("prescription", []))
    prescription = None
    if isinstance(prescription_items, list) and prescription_items:
        prescription = EMRPrescription(
            consultation_id=consultation.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            system_type=system_type,
            status="active",
            notes=str(merged.get("treatment_plan", "")),
            items_json=prescription_items,
        )
        db.add(prescription)

    write_emr_audit_log(
        db,
        doctor.id,
        "ambient_emr_saved",
        "consultation",
        consultation.id,
        patient.id,
        {"session_id": session_id, "system_type": system_type},
        "",
        "",
    )
    commit_with_retry(db)
    active_sessions.pop(session_id, None)

    return {
        "success": True,
        "consultation": serialize_consultation(consultation),
        "prescription": serialize_prescription(prescription) if prescription is not None else None,
        "redirect_url": f"/emr/patient/{patient.id}",
    }
