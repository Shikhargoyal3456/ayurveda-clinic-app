from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.auth import get_current_doctor
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient, PatientQuery
from services.ai_provider import call_ai_json_with_retry
from services.emergency_response import analyze_patient_emergency, send_doctor_emergency_alert
from services.hospital_locator import build_emergency_hospital_summary


logger = logging.getLogger(__name__)
router = APIRouter(tags=["patient-whatsapp"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _require_admin(doctor: Doctor) -> Doctor:
    configured = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    allowed_admins = configured or ["admin@ayurveda.com"]
    dev_admin_by_id = not settings.is_production and int(getattr(doctor, "id", 0) or 0) == 1
    if (doctor.username or "").strip().lower() not in allowed_admins and not dev_admin_by_id:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return doctor


def _normalize_phone(phone: str) -> str:
    digits = "".join(character for character in str(phone or "") if character.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits


def _display_phone(chat_id: str) -> str:
    return _normalize_phone(str(chat_id or "").replace("@c.us", ""))


def _find_patient_by_phone(db: Session, chat_id: str) -> Patient | None:
    normalized = _display_phone(chat_id)
    if not normalized:
        return None
    for patient in db.query(Patient).all():
        if _normalize_phone(patient.phone or "") == normalized:
            return patient
    return None


def _latest_case_summary(db: Session, patient_id: int) -> str:
    case = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient_id)
        .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
        .first()
    )
    if case is None:
        return "No recent case summary."
    return f"Recent case: diagnosis={case.diagnosis}; symptoms={case.symptoms}; notes={case.notes or 'none'}"


async def _extract_patient_understanding(patient: Patient | None, message: str, history_summary: str) -> dict[str, Any]:
    patient_block = {
        "name": getattr(patient, "name", "") or "Unknown",
        "age": getattr(patient, "age", "") or "unknown",
        "gender": getattr(patient, "gender", "") or "unknown",
        "history": history_summary,
    }
    user_prompt = f"""
Patient context:
{json.dumps(patient_block, ensure_ascii=True)}

Incoming WhatsApp message:
{message}

Return valid JSON with:
- summary: one sentence
- symptoms: array of symptom phrases
- concerns: array of concern phrases
- emotional_tone: calm, anxious, panicked, distressed, or unknown
- response_language: English or Hindi
- follow_up_needed: boolean
"""
    simpler_prompt = f"Message: {message}\nReturn JSON with summary, symptoms, concerns, emotional_tone, response_language, follow_up_needed."
    try:
        payload, provider = await call_ai_json_with_retry(
            system_prompt=(
                "You are Dr. Kash AI using Groq to understand a patient WhatsApp message. "
                "Extract symptoms, concerns, and tone. Return JSON only."
            ),
            user_prompt=user_prompt,
            simpler_user_prompt=simpler_prompt,
            temperature=0.2,
            max_output_tokens=500,
        )
        payload["provider"] = provider
        return payload
    except Exception as exc:
        logger.warning("Patient understanding AI fallback triggered: %s", exc)
        return {
            "summary": str(message or "").strip()[:180],
            "symptoms": [],
            "concerns": [str(message or "").strip()[:180]],
            "emotional_tone": "unknown",
            "response_language": "English",
            "follow_up_needed": True,
            "provider": "fallback",
        }


async def build_patient_whatsapp_reply(
    *,
    patient: Patient | None,
    doctor: Doctor | None,
    message: str,
    analysis: dict[str, Any],
    understanding: dict[str, Any],
) -> str:
    severity = str(analysis.get("severity") or "normal").lower()
    symptoms = understanding.get("symptoms") if isinstance(understanding.get("symptoms"), list) else []
    concerns = understanding.get("concerns") if isinstance(understanding.get("concerns"), list) else []
    calming = analysis.get("calming", {}) if isinstance(analysis.get("calming"), dict) else {}
    hospital = analysis.get("hospital", {}) if isinstance(analysis.get("hospital"), dict) else {}
    user_prompt = f"""
Patient name: {getattr(patient, 'name', '') or 'Patient'}
Doctor name: {getattr(doctor, 'full_name', '') or getattr(doctor, 'username', '') or 'Doctor'}
Incoming message: {message}
Severity: {severity}
Symptoms: {json.dumps(symptoms, ensure_ascii=True)}
Concerns: {json.dumps(concerns, ensure_ascii=True)}
Calming message seed: {calming.get('calming_message') or ''}
Hospital summary: {hospital.get('summary') or ''}
Safety line: {calming.get('safety_line') or ''}
Preferred language: {understanding.get('response_language') or 'English'}

Write one WhatsApp reply for the patient.
Rules:
- Calm, reassuring, short paragraphs.
- If severity is emergency, begin with a warning sign and tell them to call 112 immediately.
- Include 108 for ambulance support in emergency or urgent cases.
- Mention the nearest hospital summary when severity is emergency.
- Do not say you have dispatched an ambulance.
- End with one follow-up question if useful.
"""
    try:
        reply, _provider = await call_ai_json_with_retry(
            system_prompt=(
                "You are Dr. Kash AI using Groq to draft a WhatsApp patient response. "
                "Return valid JSON with one key: reply."
            ),
            user_prompt=user_prompt + "\nReturn valid JSON with key reply.",
            simpler_user_prompt=f"Message: {message}\nSeverity: {severity}\nReturn JSON with key reply.",
            temperature=0.3,
            max_output_tokens=450,
        )
        text = str(reply.get("reply") or "").strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Patient WhatsApp reply generation fell back: %s", exc)

    calming_message = str(calming.get("calming_message") or "Stay calm. I am here with you.").strip()
    follow_up = str(analysis.get("follow_up_question") or "Where are you right now?").strip()
    if severity == "emergency":
        return (
            f"⚠️ {calming_message}\n\n"
            f"I am detecting a possible emergency. Please call 112 right now, or 108 for ambulance support.\n"
            f"{hospital.get('summary') or 'Go to the nearest hospital immediately.'}\n\n"
            f"{follow_up}"
        )
    if severity == "urgent":
        return (
            f"{calming_message}\n\n"
            "Your symptoms may need urgent doctor review today. Please call 112 if breathing, pain, bleeding, or weakness gets worse. "
            "You can also use 108 for ambulance support.\n\n"
            f"{follow_up}"
        )
    return (
        f"{calming_message}\n\n"
        "I’ve understood your concern and I’m noting it for your care team. "
        f"{follow_up}"
    )


async def process_patient_whatsapp_message(
    *,
    db: Session,
    chat_id: str,
    message_body: str,
    request: Request | None = None,
) -> dict[str, Any]:
    patient = _find_patient_by_phone(db, chat_id)
    doctor = db.get(Doctor, patient.doctor_id) if patient else None
    history_summary = _latest_case_summary(db, patient.id) if patient else "Patient not matched in clinic records."
    understanding = await _extract_patient_understanding(patient, message_body, history_summary)
    analysis = await analyze_patient_emergency(patient=patient, doctor=doctor, message=message_body)
    if not patient:
        hospital = build_emergency_hospital_summary()
        reply = (
            "I could not find your patient record yet, but I can still help with safety guidance.\n\n"
            "If this is a medical emergency, call 112 or 108 immediately. "
            f"{hospital.get('summary')}"
        )
        return {
            "reply": reply,
            "severity": analysis.get("severity") or "normal",
            "patient": None,
            "doctor_alerted": False,
            "understanding": understanding,
            "analysis": analysis,
        }

    reply = await build_patient_whatsapp_reply(
        patient=patient,
        doctor=doctor,
        message=message_body,
        analysis=analysis,
        understanding=understanding,
    )
    query = PatientQuery(
        patient_id=patient.id,
        doctor_id=patient.doctor_id,
        source_channel="whatsapp",
        query_text=message_body.strip(),
        ai_response=reply,
        severity=str(analysis.get("severity") or "normal"),
        ai_tag=str(analysis.get("severity") or "normal").upper(),
        fallback_tag="EMERGENCY" if analysis.get("keyword_hits") else None,
        matched_keywords=json.dumps(analysis.get("keyword_hits") or [], ensure_ascii=True),
        alert_sent=0,
    )
    db.add(query)
    commit_with_retry(db)
    db.refresh(query)

    doctor_alerted = False
    if analysis.get("severity") in {"emergency", "urgent"}:
        alert_result = await send_doctor_emergency_alert(
            doctor=doctor,
            patient=patient,
            patient_phone=_display_phone(chat_id),
            analysis=analysis,
        )
        doctor_alerted = bool(
            (alert_result.get("email") or {}).get("success")
            or (alert_result.get("whatsapp") or {}).get("success")
            or bool((alert_result.get("whatsapp") or {}).get("id"))
        )
        if doctor_alerted:
            query.alert_sent = 1
            query.notified_at = datetime.now(timezone.utc)
            commit_with_retry(db)

    if request is not None:
        write_audit_event(
            "patient_whatsapp_processed",
            request,
            patient_id=patient.id,
            doctor_id=patient.doctor_id,
            query_id=query.id,
            severity=query.severity,
            doctor_alerted=doctor_alerted,
        )

    return {
        "reply": reply,
        "severity": query.severity,
        "patient": {"id": patient.id, "name": patient.name},
        "doctor_alerted": doctor_alerted,
        "understanding": understanding,
        "analysis": analysis,
        "query_id": query.id,
    }


@router.get("/admin/emergency-responses", response_class=HTMLResponse)
def emergency_response_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    rows = (
        db.query(PatientQuery)
        .filter(PatientQuery.source_channel == "whatsapp")
        .order_by(PatientQuery.created_at.desc(), PatientQuery.id.desc())
        .limit(30)
        .all()
    )
    items = []
    for row in rows:
        patient = db.get(Patient, row.patient_id)
        items.append(
            {
                "patient_name": patient.name if patient else "Unknown patient",
                "severity": row.severity,
                "query_text": row.query_text,
                "ai_response": row.ai_response,
                "alert_sent": bool(row.alert_sent),
                "created_at": row.created_at,
            }
        )
    return templates.TemplateResponse(
        "emergency_response.html",
        {
            "request": request,
            "items": items,
        },
    )


@router.post("/api/patient-whatsapp/process")
async def process_patient_whatsapp_api(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    chat_id = str(payload.get("chat_id") or payload.get("chatId") or payload.get("from") or "").strip()
    body = re.sub(r"\s+", " ", str(payload.get("body") or payload.get("message") or "")).strip()
    result = await process_patient_whatsapp_message(db=db, chat_id=chat_id, message_body=body, request=request)
    return JSONResponse({"success": True, **result})
