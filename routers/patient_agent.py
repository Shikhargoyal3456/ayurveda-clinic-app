from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.auth import get_current_doctor
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient, PatientQuery, PendingReview
from models.prescription import Prescription
from services.ai_provider import call_gemini, is_gemini_configured
from services.doctor_notifier import notify_doctor_of_alert, notify_doctor_pending_review
from services.emergency_detector import EmergencyAssessment, assess_emergency


logger = logging.getLogger(__name__)
router = APIRouter(tags=["patient-agent"])
TAG_PATTERN = re.compile(r"^\s*\[(EMERGENCY|URGENT|NORMAL)\]\s*", re.IGNORECASE)
MAX_MESSAGE_CHARS = 2000


class PatientAgentRequest(BaseModel):
    patient_id: int | None = None
    patient_phone: str | None = None
    patient_name: str | None = None
    message: str = Field(..., min_length=3, max_length=MAX_MESSAGE_CHARS)
    channel: str = "app"


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:MAX_MESSAGE_CHARS]


def _normalize_phone(phone: str) -> str:
    digits = "".join(character for character in str(phone or "") if character.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits


def _find_patient(db: Session, payload: PatientAgentRequest) -> Patient:
    patient = None
    if payload.patient_id is not None:
        patient = db.get(Patient, payload.patient_id)
    if patient is None and payload.patient_phone:
        normalized_phone = _normalize_phone(payload.patient_phone)
        candidates = db.query(Patient).all()
        patient = next((item for item in candidates if _normalize_phone(item.phone or "") == normalized_phone), None)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


def _recent_case_context(db: Session, patient_id: int) -> list[CaseSheet]:
    return (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient_id)
        .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
        .limit(3)
        .all()
    )


def _recent_prescription_context(db: Session, patient_id: int) -> list[Prescription]:
    return (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(2)
        .all()
    )


def _build_history_block(cases: list[CaseSheet], prescriptions: list[Prescription]) -> str:
    lines: list[str] = []
    for case in cases:
        lines.append(
            f"- Case on {(case.created_at or datetime.now(timezone.utc)).strftime('%d %b %Y')}: "
            f"diagnosis={case.diagnosis}; symptoms={case.symptoms}; notes={case.notes or 'none'}"
        )
    for prescription in prescriptions:
        medicines = ", ".join(str(item.get("name") or "").strip() for item in (prescription.medicines or []) if isinstance(item, dict))
        lines.append(
            f"- Prescription on {(prescription.created_at or datetime.now(timezone.utc)).strftime('%d %b %Y')}: "
            f"diagnosis={prescription.diagnosis}; medicines={medicines or 'none'}; advice={prescription.advice or 'none'}"
        )
    return "\n".join(lines) if lines else "- No prior case or prescription history available."


def _build_prompt(patient: Patient, cases: list[CaseSheet], prescriptions: list[Prescription], message: str) -> str:
    history_block = _build_history_block(cases, prescriptions)
    return f"""
You are Dr. Kash, an AI patient support agent for a clinic. You help patients using their history, but you do not replace a doctor.

Return your reply in this exact format:
[EMERGENCY] response
or
[URGENT] response
or
[NORMAL] response

Rules:
- Use EMERGENCY for chest pain, severe breathing difficulty, stroke signs, heavy bleeding, seizures, suicidal intent, collapse, or any life-threatening pattern.
- Use URGENT for worsening fever, severe dehydration, persistent vomiting, severe pain, pregnancy bleeding, or same-day doctor review.
- Use NORMAL for routine, non-dangerous questions.
- Be warm and short.
- Never prescribe a new medicine dose.
- If EMERGENCY, tell the patient to call 112 immediately.
- Mention prior history only when relevant.

Patient:
- Name: {patient.name}
- Age: {patient.age}
- Gender: {patient.gender}

Recent history:
{history_block}

Patient message:
{message}
""".strip()


def _extract_tagged_reply(raw_text: str) -> tuple[str, str]:
    text = str(raw_text or "").strip()
    match = TAG_PATTERN.match(text)
    if not match:
        return "NORMAL", text or "Please contact your doctor if symptoms are worsening."
    tag = match.group(1).upper()
    reply = TAG_PATTERN.sub("", text, count=1).strip()
    return tag, reply


def _safe_reply_for_failure(message: str) -> tuple[str, str]:
    assessment = assess_emergency(message, "NORMAL")
    if assessment.severity == "emergency":
        return "EMERGENCY", "This may be serious. Please call 112 immediately or go to the nearest emergency department."
    if assessment.severity == "urgent":
        return "URGENT", "This needs timely doctor review. Please contact your clinic today or seek urgent medical care if symptoms worsen."
    return "NORMAL", "I could not analyze this fully right now. Please rest, monitor your symptoms, and contact your doctor if things are getting worse."


async def _notify_if_needed(db: Session, doctor: Doctor, patient: Patient, query: PatientQuery) -> bool:
    if query.severity not in {"emergency", "urgent"}:
        return False
    try:
        result = await notify_doctor_of_alert(doctor, patient, query)
        if result.get("success"):
            query.alert_sent = 1
            query.notified_at = datetime.now(timezone.utc)
            commit_with_retry(db)
            return True
    except Exception as exc:  # pragma: no cover
        logger.exception("Doctor alert notification failed: %s", exc)
    return False


@router.post("/api/patient-agent/ask")
async def patient_agent_ask(
    payload: PatientAgentRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    patient = _find_patient(db, payload)
    doctor = db.get(Doctor, patient.doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found for patient.")

    message = _clean_text(payload.message)
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    ai_tag = "NORMAL"
    ai_reply = ""
    try:
        if not is_gemini_configured():
            raise RuntimeError("Gemini is not configured.")
        raw = await call_gemini(
            _build_prompt(patient, _recent_case_context(db, patient.id), _recent_prescription_context(db, patient.id), message),
            system_prompt="You are a careful clinic patient support assistant. Always begin with one bracketed tag: [EMERGENCY], [URGENT], or [NORMAL].",
            temperature=0.2,
            max_output_tokens=350,
        )
        ai_tag, ai_reply = _extract_tagged_reply(raw)
    except Exception as exc:
        logger.warning("Patient agent Gemini call failed: %s", exc)
        ai_tag, ai_reply = _safe_reply_for_failure(message)

    assessment: EmergencyAssessment = assess_emergency(message, ai_tag)
    final_severity = assessment.severity
    final_reply = ai_reply
    if final_severity == "emergency" and "112" not in final_reply:
        final_reply = f"Please call 112 immediately. {final_reply}".strip()
    elif final_severity == "urgent" and "doctor" not in final_reply.lower():
        final_reply = f"{final_reply} Please contact your doctor soon.".strip()

    query = PatientQuery(
        patient_id=patient.id,
        doctor_id=doctor.id,
        source_channel=_clean_text(payload.channel or "app").lower() or "app",
        query_text=message,
        ai_response=final_reply,
        severity=final_severity,
        ai_tag=assessment.ai_tag,
        fallback_tag=assessment.fallback_tag,
        matched_keywords=json.dumps(assessment.matched_keywords, ensure_ascii=True) if assessment.matched_keywords else None,
    )
    db.add(query)
    commit_with_retry(db)
    db.refresh(query)

    review = PendingReview(
        patient_id=patient.id,
        doctor_id=doctor.id,
        query_id=query.id,
        question=message,
        ai_suggestion=final_reply,
        status="pending",
    )
    db.add(review)
    commit_with_retry(db)
    db.refresh(review)

    pending_notified = await notify_doctor_pending_review(doctor, patient, review)
    alert_notified = await _notify_if_needed(db, doctor, patient, query)
    write_audit_event(
        "patient_agent_review_created",
        request,
        patient_id=patient.id,
        doctor_id=doctor.id,
        query_id=query.id,
        review_id=review.id,
        severity=final_severity,
    )

    safe_patient_message = (
        "Thank you for your question. Your doctor has been notified and will review the reply shortly before anything is sent to you."
    )
    if final_severity == "emergency":
        safe_patient_message = (
            "Thank you. Your doctor has been notified for urgent review. If this feels like a medical emergency, call 112 immediately."
        )
    elif final_severity == "urgent":
        safe_patient_message = (
            "Thank you. Your doctor has been notified for priority review and will respond shortly."
        )

    return JSONResponse(
        {
            "success": True,
            "query_id": query.id,
            "review_id": review.id,
            "severity": final_severity,
            "reply": safe_patient_message,
            "review_required": True,
            "doctor_alerted": bool(alert_notified or pending_notified.get("success")),
            "disclaimer": "AI has prepared a draft. Your doctor will review and approve it before you receive any medical response.",
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "doctor_id": doctor.id,
            },
        }
    )


@router.get("/api/doctor/{doctor_id}/alerts")
async def doctor_patient_alerts(
    doctor_id: int,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    if doctor.id != doctor_id:
        raise HTTPException(status_code=403, detail="You can only view your own alerts.")
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    rows = (
        db.query(PatientQuery)
        .filter(
            PatientQuery.doctor_id == doctor.id,
            PatientQuery.severity.in_(["emergency", "urgent"]),
            PatientQuery.created_at >= cutoff,
        )
        .order_by(PatientQuery.created_at.desc(), PatientQuery.id.desc())
        .limit(20)
        .all()
    )
    payload = []
    for row in rows:
        patient = db.get(Patient, row.patient_id)
        if patient is None:
            continue
        payload.append(
            {
                "id": row.id,
                "severity": row.severity,
                "patient_id": patient.id,
                "patient_name": patient.name,
                "patient_phone": patient.phone or "",
                "source_channel": row.source_channel,
                "query_text": row.query_text,
                "ai_response": row.ai_response,
                "alert_sent": bool(row.alert_sent),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return JSONResponse({"success": True, "alerts": payload})
