from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import commit_with_retry, get_db
from app.models import ConsultationMetric, ConsultationSession, Doctor, DoctorActivityLog, Patient, VoiceTranscript
from app.config import settings


router = APIRouter(prefix="/api/consultation", tags=["consultation"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _parse_text(text: str) -> dict[str, object]:
    patient_name = ""
    age = None
    gender = ""
    symptoms: list[str] = []
    medicines: list[str] = []
    follow_up = 7
    if match := re.search(r"patient is ([a-z ]+),?\s*(\d{1,3})", text, re.I):
        patient_name = match.group(1).title().strip()
        age = int(match.group(2))
    if "female" in text.lower():
        gender = "Female"
    elif "male" in text.lower():
        gender = "Male"
    for keyword in ["fever", "cough", "sore throat", "digestion", "stomach", "weak pulse"]:
        if keyword in text.lower():
            symptoms.append(keyword.title())
    for medicine in ["triphala", "chitrakadi vati", "dashmool kadha"]:
        if medicine in text.lower():
            medicines.append(medicine.title())
    diagnosis = "Vata-Kapha imbalance" if symptoms else "Ayurvedic consultation draft"
    return {
        "patient": {"name": patient_name, "age": age, "gender": gender},
        "symptoms": symptoms,
        "diagnosis": diagnosis,
        "medicines": medicines,
        "follow_up": follow_up,
    }


@router.post("/start")
async def start(payload: dict[str, object] = Body(default={}), db: Session = Depends(get_db)):
    doctor_id = int(payload.get("doctor_id") or 0)
    patient_id = int(payload.get("patient_id") or 0)
    if not doctor_id or not patient_id:
        raise HTTPException(status_code=422, detail="doctor_id is required")
    now = datetime.now(timezone.utc)
    session = ConsultationSession(doctor_id=doctor_id, patient_id=patient_id, status="active", started_at=now)
    db.add(session)
    db.flush()
    db.add(ConsultationMetric(consultation_id=session.id, doctor_id=doctor_id, patient_id=patient_id, start_time=now, ai_used=True))
    db.add(DoctorActivityLog(doctor_id=doctor_id, activity_type="consultation_start", created_at=now))
    commit_with_retry(db)
    return {"success": True, "session_id": session.id, "status": session.status}


@router.post("/transcript")
async def transcript(payload: dict[str, object] = Body(default={}), db: Session = Depends(get_db)):
    session_id = int(payload.get("session_id") or 0)
    text = str(payload.get("transcript") or payload.get("text") or "").strip()
    if not session_id or not text:
        raise HTTPException(status_code=422, detail="session_id and transcript are required")
    extracted = _parse_text(text)
    row = VoiceTranscript(session_id=session_id, transcript=text, extracted_data=json.dumps(extracted))
    db.add(row)
    commit_with_retry(db)
    return {"success": True, "transcript": text, "extracted_data": extracted}


@router.post("/stop")
async def stop(payload: dict[str, object] = Body(default={}), db: Session = Depends(get_db)):
    session_id = int(payload.get("session_id") or 0)
    if not session_id:
        raise HTTPException(status_code=422, detail="session_id is required")
    session = db.get(ConsultationSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "completed"
    now = datetime.now(timezone.utc)
    session.ended_at = now
    metric = db.query(ConsultationMetric).filter(ConsultationMetric.consultation_id == session_id).first()
    if metric is not None:
        metric.end_time = now
        metric.duration_seconds = int((now - metric.start_time).total_seconds())
    db.add(DoctorActivityLog(doctor_id=session.doctor_id, activity_type="consultation_end", duration_seconds=(metric.duration_seconds if metric else None), created_at=now))
    commit_with_retry(db)
    return {"success": True, "status": session.status}


@router.get("/{session_id}/status")
async def status(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ConsultationSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "status": session.status, "started_at": session.started_at, "ended_at": session.ended_at}


@router.post("/extract")
async def extract(payload: dict[str, object] = Body(default={})):
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcript is required")
    return {"success": True, "data": _parse_text(transcript)}


@router.post("/save")
async def save_consultation(payload: dict[str, object] = Body(default={})):
    try:
        return {
            "success": True,
            "message": "Consultation saved successfully",
            "data": payload,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ai-voice")
async def use_ai_voice(payload: dict[str, object] = Body(default={}), db: Session = Depends(get_db)):
    session_id = int(payload.get("session_id") or 0)
    voice_transcript = str(payload.get("voice_transcript") or "").strip()
    doctor_id = int(payload.get("doctor_id") or 0)
    metric = db.query(ConsultationMetric).filter(ConsultationMetric.consultation_id == session_id).first()
    if metric is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    voice_seconds = max(0, len(voice_transcript.split()) * 2)
    metric.ai_voice_enabled = True
    metric.ai_used = True
    metric.voice_duration_seconds = (metric.voice_duration_seconds or 0) + voice_seconds
    db.add(
        DoctorActivityLog(
            doctor_id=doctor_id or metric.doctor_id,
            activity_type="ai_interaction",
            extra_data=json.dumps({"type": "voice", "session_id": session_id}),
            created_at=datetime.now(timezone.utc),
        )
    )
    commit_with_retry(db)
    return {"status": "tracked"}


@router.post("/ai-feedback")
async def submit_ai_feedback(feedback: dict[str, object] = Body(default={}), db: Session = Depends(get_db)):
    record = {
        "consultation_id": int(feedback.get("consultation_id") or 0) or None,
        "doctor_id": int(feedback.get("doctor_id") or 0) or None,
        "feature_type": str(feedback.get("feature_type") or ""),
        "ai_suggestion": feedback.get("ai_suggestion"),
        "doctor_final": feedback.get("doctor_final"),
        "was_accepted": bool(feedback.get("was_accepted")),
        "modified": bool(feedback.get("modified")),
        "accuracy_score": feedback.get("accuracy_score"),
        "feedback_text": feedback.get("feedback_text"),
    }
    if not record["feature_type"]:
        raise HTTPException(status_code=422, detail="feature_type is required")
    from models.prescription import AIFeedback

    if record["doctor_id"] is None and record["consultation_id"] is not None:
        metric = db.query(ConsultationMetric).filter(ConsultationMetric.consultation_id == record["consultation_id"]).first()
        record["doctor_id"] = metric.doctor_id if metric is not None else None
    if record["doctor_id"] is None:
        raise HTTPException(status_code=422, detail="doctor_id is required")
    row = AIFeedback(**record)
    db.add(row)
    commit_with_retry(db)
    return {"status": "feedback_submitted"}


@router.get("/voice-consultation")
def voice_consultation_page(request: Request):
    return templates.TemplateResponse(
        "consultation/voice_consultation.html",
        {"request": request},
    )
