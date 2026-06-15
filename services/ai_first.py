from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Appointment, CaseSheet, Doctor, Patient
from models.prescription import AIFeedback, Prescription
from services.ai_provider import call_gemini, parse_json_response
from services.cache_service import cache


def _text(value: object, fallback: str = "") -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    return cleaned or fallback


def _symptom_tokens(value: object) -> list[str]:
    text = str(value or "").replace("\n", ",")
    raw_parts = re.split(r",|;|\band\b", text, flags=re.IGNORECASE)
    seen: list[str] = []
    for part in raw_parts:
        cleaned = re.sub(r"^[\-\*\d\.\s]+", "", part).strip(" .:")
        if cleaned and cleaned.lower() not in {item.lower() for item in seen}:
            seen.append(cleaned)
    return seen[:6]


def get_doctor_preferences(db: Session, doctor_id: int, limit: int = 18) -> str:
    rows = (
        db.query(AIFeedback)
        .filter(
            AIFeedback.doctor_id == doctor_id,
            AIFeedback.field_name.is_not(None),
            AIFeedback.ai_suggestion.is_not(None),
            AIFeedback.doctor_correction.is_not(None),
        )
        .order_by(AIFeedback.created_at.desc(), AIFeedback.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return "No recorded correction preferences yet."

    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        field_name = _text(row.field_name, "general")
        ai_text = _text(row.ai_suggestion)
        doctor_text = _text(row.doctor_correction)
        if not ai_text or not doctor_text or ai_text == doctor_text:
            continue
        grouped[field_name].append(f"AI suggested '{ai_text[:90]}', doctor changed to '{doctor_text[:90]}'.")

    if not grouped:
        return "No recorded correction preferences yet."
    return "\n".join(
        f"{field}: {' '.join(examples[:3])}"
        for field, examples in grouped.items()
    )


def _estimate_duration_minutes(cases: list[CaseSheet]) -> int:
    if not cases:
        return 10
    latest = cases[0]
    complexity = len(_symptom_tokens(latest.symptoms)) + (2 if _text(latest.followup_notes) else 0)
    chronic_markers = sum(
        1
        for marker in ("chronic", "recurrent", "worsening", "insomnia", "pain", "fatigue")
        if marker in _text(latest.notes).lower() or marker in _text(latest.diagnosis).lower()
    )
    return max(8, min(20, 8 + complexity + chronic_markers))


def _history_fallback(patient: Patient, cases: list[CaseSheet], prescriptions: list[Prescription]) -> dict[str, Any]:
    specialty = _text(getattr(getattr(patient, "doctor", None), "specialty", ""), "ayurveda").lower()
    if specialty in {"modern_medicine", "dental", "physiotherapy"}:
        consultation_url = f"/emr/modern-consultation/{patient.id}"
    elif specialty == "ayurveda":
        consultation_url = f"/emr/ayurveda-consultation/{patient.id}"
    else:
        consultation_url = f"/emr/integrated-consultation/{patient.id}"
    latest_case = cases[0] if cases else None
    previous_prescription = prescriptions[0] if prescriptions else None
    prescription_names = []
    if previous_prescription:
        for item in previous_prescription.medicines or []:
            if isinstance(item, dict):
                name = _text(item.get("name"))
                if name:
                    prescription_names.append(name)
    followup_warning = None
    if latest_case and latest_case.followup_date and latest_case.followup_date < date.today():
        delta = (date.today() - latest_case.followup_date).days
        followup_warning = f"Follow-up was due {delta} day{'s' if delta != 1 else ''} ago."
    bullets = []
    if latest_case:
        bullets.append(
            f"Last visit: {latest_case.created_at.strftime('%d %b %Y')} for {_text(latest_case.diagnosis, 'review')}"
        )
        symptoms = ", ".join(_symptom_tokens(latest_case.symptoms)[:3])
        if symptoms:
            bullets.append(f"Common symptoms last time: {symptoms}")
    if prescription_names:
        bullets.append(f"Previous prescription: {', '.join(prescription_names[:3])}")
    if followup_warning:
        bullets.append(followup_warning)
    if not bullets:
        bullets.append(f"{patient.name} has limited prior history. Start with a fresh assessment.")
    return {
        "bullets": bullets[:4],
        "consultation_minutes": _estimate_duration_minutes(cases),
        "cta_primary": {"label": "Start follow-up consultation", "url": consultation_url},
        "cta_secondary": {"label": "View full history", "url": f"/patients/{patient.id}/cases"},
    }


async def generate_patient_history_insights(db: Session, doctor_id: int, patient_id: int) -> dict[str, Any]:
    cache_key = f"ai:first:patient-history:{doctor_id}:{patient_id}"
    cached = await cache.get_json_async(cache_key)
    if isinstance(cached, dict) and cached.get("bullets"):
        return cached

    patient = (
        db.query(Patient)
        .options(joinedload(Patient.cases), joinedload(Patient.doctor))
        .filter(Patient.id == patient_id, Patient.doctor_id == doctor_id)
        .first()
    )
    if patient is None:
        raise ValueError("Patient not found.")

    cases = sorted(list(patient.cases or []), key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id, Prescription.doctor_id == doctor_id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(5)
        .all()
    )
    fallback = _history_fallback(patient, cases, prescriptions)

    history_blob = []
    for case in cases[:5]:
        history_blob.append(
            {
                "date": case.created_at.date().isoformat() if case.created_at else "",
                "diagnosis": _text(case.diagnosis),
                "symptoms": _symptom_tokens(case.symptoms),
                "notes": _text(case.notes),
                "followup_date": case.followup_date.isoformat() if case.followup_date else "",
                "followup_notes": _text(case.followup_notes),
            }
        )
    prescription_blob = []
    for prescription in prescriptions[:3]:
        meds = []
        for item in prescription.medicines or []:
            if isinstance(item, dict):
                name = _text(item.get("name"))
                if name:
                    meds.append(name)
        if meds:
            prescription_blob.append({"date": prescription.created_at.date().isoformat() if prescription.created_at else "", "medicines": meds[:4]})

    prompt = (
        "You are Kash AI, an invisible clinic copilot. Read the patient's case history and return compact JSON only.\n"
        "Return keys: bullets (array of 3-4 bullets), consultation_minutes (integer 8-20), "
        "cta_primary (object with label and url), cta_secondary (object with label and url).\n"
        "Rules: be specific, proactive, concise, and safe. Mention overdue follow-up if applicable.\n\n"
        f"Patient: {patient.name}, age {patient.age}, gender {patient.gender}\n"
        f"Case history: {json.dumps(history_blob, ensure_ascii=True)}\n"
        f"Prescription history: {json.dumps(prescription_blob, ensure_ascii=True)}"
    )

    payload = fallback
    try:
        raw = await call_gemini(
            prompt,
            system_prompt="You generate proactive doctor-facing patient insights. Return valid JSON only.",
            temperature=0.2,
            response_mime_type="application/json",
            max_output_tokens=400,
        )
        parsed = parse_json_response(raw)
        payload = {
            "bullets": [str(item).strip() for item in parsed.get("bullets", []) if str(item).strip()][:4] or fallback["bullets"],
            "consultation_minutes": int(parsed.get("consultation_minutes") or fallback["consultation_minutes"]),
            "cta_primary": parsed.get("cta_primary") or fallback["cta_primary"],
            "cta_secondary": parsed.get("cta_secondary") or fallback["cta_secondary"],
        }
    except Exception:
        payload = fallback

    await cache.set_json_async(cache_key, payload, ttl_seconds=3600)
    return payload


async def generate_case_prefill(db: Session, doctor_id: int, patient_id: int) -> dict[str, Any]:
    cache_key = f"ai:first:case-prefill:{doctor_id}:{patient_id}"
    cached = await cache.get_json_async(cache_key)
    if isinstance(cached, dict) and cached.get("fields"):
        return cached

    patient = (
        db.query(Patient)
        .options(joinedload(Patient.cases), joinedload(Patient.doctor))
        .filter(Patient.id == patient_id, Patient.doctor_id == doctor_id)
        .first()
    )
    if patient is None:
        raise ValueError("Patient not found.")

    recent_cases = sorted(list(patient.cases or []), key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:3]
    if not recent_cases:
        payload = {
            "summary": "Kash AI will learn from this patient's next consultation.",
            "fields": {},
            "cards": [],
            "consultation_minutes": 10,
        }
        await cache.set_json_async(cache_key, payload, ttl_seconds=3600)
        return payload

    fallback_fields = {
        "prakriti": _text(recent_cases[0].prakriti),
        "diagnosis": _text(recent_cases[0].diagnosis),
        "symptoms": ", ".join(_symptom_tokens(recent_cases[0].symptoms)[:4]),
        "notes": _text(recent_cases[0].notes),
        "followup_notes": _text(recent_cases[0].followup_notes),
    }
    fallback_payload = {
        "summary": "Based on recent consultations, Kash AI prepared a head start for this case sheet.",
        "fields": fallback_fields,
        "cards": [
            f"Prakriti: {fallback_fields['prakriti'] or 'Not enough history yet'}",
            f"Common symptoms: {fallback_fields['symptoms'] or 'Not enough history yet'}",
            f"Previous diagnosis: {fallback_fields['diagnosis'] or 'Not enough history yet'}",
        ],
        "consultation_minutes": _estimate_duration_minutes(recent_cases),
    }
    doctor_preferences = get_doctor_preferences(db, doctor_id)
    case_blob = [
        {
            "date": case.created_at.date().isoformat() if case.created_at else "",
            "prakriti": _text(case.prakriti),
            "diagnosis": _text(case.diagnosis),
            "symptoms": _symptom_tokens(case.symptoms),
            "notes": _text(case.notes),
            "followup_notes": _text(case.followup_notes),
        }
        for case in recent_cases
    ]
    prompt = (
        "You are Kash AI pre-filling a doctor's case sheet from the last three consultations. Return JSON only.\n"
        "Return keys: summary, consultation_minutes, cards (array of 3 short strings), fields (object with prakriti, diagnosis, symptoms, notes, followup_notes).\n"
        "Keep fields editable and concise. Use doctor's preferences when relevant.\n\n"
        f"Patient: {patient.name}, age {patient.age}, gender {patient.gender}\n"
        f"Recent cases: {json.dumps(case_blob, ensure_ascii=True)}\n"
        f"Doctor preferences:\n{doctor_preferences}"
    )

    payload = fallback_payload
    try:
        raw = await call_gemini(
            prompt,
            system_prompt="You are a proactive clinical documentation copilot. Return valid JSON only.",
            temperature=0.2,
            response_mime_type="application/json",
            max_output_tokens=500,
        )
        parsed = parse_json_response(raw)
        fields = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else {}
        payload = {
            "summary": _text(parsed.get("summary"), fallback_payload["summary"]),
            "fields": {
                "prakriti": _text(fields.get("prakriti"), fallback_fields["prakriti"]),
                "diagnosis": _text(fields.get("diagnosis"), fallback_fields["diagnosis"]),
                "symptoms": _text(fields.get("symptoms"), fallback_fields["symptoms"]),
                "notes": _text(fields.get("notes"), fallback_fields["notes"]),
                "followup_notes": _text(fields.get("followup_notes"), fallback_fields["followup_notes"]),
            },
            "cards": [str(item).strip() for item in parsed.get("cards", []) if str(item).strip()][:3] or fallback_payload["cards"],
            "consultation_minutes": int(parsed.get("consultation_minutes") or fallback_payload["consultation_minutes"]),
        }
    except Exception:
        payload = fallback_payload

    await cache.set_json_async(cache_key, payload, ttl_seconds=3600)
    return payload


async def generate_next_actions(db: Session, doctor_id: int, patient_id: int, case_id: int | None = None) -> dict[str, Any]:
    cache_key = f"ai:first:next-actions:{doctor_id}:{patient_id}:{case_id or 'latest'}"
    cached = await cache.get_json_async(cache_key)
    if isinstance(cached, dict) and cached.get("actions"):
        return cached

    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise ValueError("Patient not found.")

    latest_case = None
    if case_id is not None:
        latest_case = db.query(CaseSheet).filter(CaseSheet.id == case_id, CaseSheet.patient_id == patient_id).first()
    if latest_case is None:
        latest_case = (
            db.query(CaseSheet)
            .filter(CaseSheet.patient_id == patient_id)
            .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
            .first()
        )

    prescriptions_count = (
        db.query(func.count(Prescription.id))
        .filter(Prescription.patient_id == patient_id, Prescription.doctor_id == doctor_id)
        .scalar()
        or 0
    )
    appointments_count = (
        db.query(func.count(Appointment.id))
        .filter(Appointment.patient_id == patient_id)
        .scalar()
        or 0
    )
    actions = [
        {"label": "Generate Prescription", "icon": "📋", "url": f"/patients/{patient_id}/prescriptions/new", "description": "Turn this consultation into a doctor-reviewed prescription."},
        {"label": "Schedule Follow-up", "icon": "📅", "url": "/appointments", "description": "Book the next touchpoint while the plan is fresh."},
        {"label": "Share via WhatsApp", "icon": "📱", "url": f"/patients/{patient_id}/cases", "description": "Open the case history and share the next steps with the patient."},
    ]
    if appointments_count > prescriptions_count:
        actions[0], actions[1] = actions[1], actions[0]
    payload = {
        "title": "What would you like to do next?",
        "actions": actions,
        "reason": _text(getattr(latest_case, "diagnosis", ""), "Recent case saved."),
    }
    await cache.set_json_async(cache_key, payload, ttl_seconds=900)
    return payload


async def generate_risk_patients(db: Session, doctor_id: int) -> dict[str, Any]:
    cache_key = f"ai:first:risk-patients:{doctor_id}:{date.today().isoformat()}"
    cached = await cache.get_json_async(cache_key)
    if isinstance(cached, dict) and cached.get("patients"):
        return cached

    patients = db.query(Patient).filter(Patient.doctor_id == doctor_id).order_by(Patient.created_at.desc()).limit(80).all()
    risk_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for patient in patients:
        recent_cases = (
            db.query(CaseSheet)
            .filter(CaseSheet.patient_id == patient.id)
            .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
            .limit(3)
            .all()
        )
        if not recent_cases:
            continue
        latest_case = recent_cases[0]
        overdue_days = (date.today() - latest_case.followup_date).days if latest_case.followup_date and latest_case.followup_date < date.today() else 0
        diagnosis_counter = Counter(_text(case.diagnosis) for case in recent_cases if _text(case.diagnosis))
        repeated = diagnosis_counter.most_common(1)[0] if diagnosis_counter else ("", 0)
        severity = None
        reason = None
        if overdue_days >= 5:
            severity = "high"
            reason = f"Follow-up overdue {overdue_days} days. {_text(latest_case.diagnosis, 'Symptoms need review')}."
        elif repeated[1] >= 3 and repeated[0]:
            severity = "medium"
            reason = f"{repeated[1]} consecutive cases around {repeated[0]}."
        if severity and reason:
            row = (
                {
                    "patient_id": patient.id,
                    "patient_name": patient.name,
                    "severity": severity,
                    "reason": reason,
                }
            )
            candidate_rows.append(row)
            risk_rows.append(row)

    risk_rows = sorted(risk_rows, key=lambda item: (0 if item["severity"] == "high" else 1, item["patient_name"]))[:6]
    payload = {"patients": risk_rows}
    if candidate_rows:
        prompt = (
            "You are Kash AI reviewing clinic risk candidates. Return JSON only with key patients.\n"
            "Choose up to 6 highest-risk patients. Keep each item with patient_id, patient_name, severity, reason.\n"
            "Use severity values high or medium. Reasons must stay short and clinically useful.\n\n"
            f"Candidates: {json.dumps(candidate_rows[:18], ensure_ascii=True)}"
        )
        try:
            raw = await call_gemini(
                prompt,
                system_prompt="You are a proactive clinic risk copilot. Return valid JSON only.",
                temperature=0.1,
                response_mime_type="application/json",
                max_output_tokens=500,
            )
            parsed = parse_json_response(raw)
            ai_rows = []
            for item in parsed.get("patients", []):
                if not isinstance(item, dict):
                    continue
                patient_id = int(item.get("patient_id") or 0)
                patient_name = _text(item.get("patient_name"), "Patient")
                severity = _text(item.get("severity"), "medium").lower()
                reason = _text(item.get("reason"))
                if patient_id and patient_name and severity in {"high", "medium"} and reason:
                    ai_rows.append(
                        {
                            "patient_id": patient_id,
                            "patient_name": patient_name,
                            "severity": severity,
                            "reason": reason,
                        }
                    )
            if ai_rows:
                payload = {"patients": ai_rows[:6]}
        except Exception:
            payload = {"patients": risk_rows}
    await cache.set_json_async(cache_key, payload, ttl_seconds=86400)
    return payload


def _fallback_assistant_search(db: Session, doctor_id: int, query: str) -> dict[str, Any]:
    lowered = _text(query).lower()
    keywords = [
        token
        for token in re.findall(r"[a-zA-Z]{3,}", lowered)
        if token not in {"show", "patients", "patient", "with", "high", "all", "me", "the", "and", "for"}
    ]
    patients = db.query(Patient).filter(Patient.doctor_id == doctor_id).order_by(Patient.name.asc()).limit(80).all()
    matches = []
    for patient in patients:
        latest_case = (
            db.query(CaseSheet)
            .filter(CaseSheet.patient_id == patient.id)
            .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
            .first()
        )
        haystack = " ".join(
            [
                _text(patient.name),
                _text(getattr(latest_case, "diagnosis", "")),
                _text(getattr(latest_case, "symptoms", "")),
                _text(getattr(latest_case, "notes", "")),
            ]
        ).lower()
        if lowered and lowered in haystack:
            matches.append(
                {
                    "patient_id": patient.id,
                    "patient_name": patient.name,
                    "summary": _text(getattr(latest_case, "diagnosis", ""), "Recent consultation available."),
                }
            )
            continue
        if keywords and all(keyword in haystack for keyword in keywords[:3]):
            matches.append(
                {
                    "patient_id": patient.id,
                    "patient_name": patient.name,
                    "summary": _text(getattr(latest_case, "diagnosis", ""), "Recent consultation available."),
                }
            )
    answer = f"I found {len(matches)} matching patient record{'s' if len(matches) != 1 else ''}."
    return {"answer": answer, "matches": matches[:8]}


async def answer_doctor_assistant_query(db: Session, doctor_id: int, query: str) -> dict[str, Any]:
    safe_query = _text(query)
    if not safe_query:
        return {"answer": "Ask Kash AI about a patient, symptom pattern, or follow-up risk.", "matches": []}

    patients = db.query(Patient).filter(Patient.doctor_id == doctor_id).order_by(Patient.created_at.desc()).limit(50).all()
    patient_blob = []
    for patient in patients:
        latest_case = (
            db.query(CaseSheet)
            .filter(CaseSheet.patient_id == patient.id)
            .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
            .first()
        )
        patient_blob.append(
            {
                "patient_id": patient.id,
                "patient_name": patient.name,
                "age": patient.age,
                "diagnosis": _text(getattr(latest_case, "diagnosis", "")),
                "symptoms": _symptom_tokens(getattr(latest_case, "symptoms", "")),
                "followup_date": latest_case.followup_date.isoformat() if latest_case and latest_case.followup_date else "",
            }
        )

    prompt = (
        "You are Kash AI helping a doctor search their clinic database. Return JSON only.\n"
        "Return keys: answer (string), matches (array of objects with patient_id, patient_name, summary).\n"
        "Only use patient rows provided. Do not invent patients.\n\n"
        f"Doctor query: {safe_query}\n"
        f"Patients: {json.dumps(patient_blob, ensure_ascii=True)}"
    )
    try:
        raw = await call_gemini(
            prompt,
            system_prompt="You answer doctor workspace queries over a provided patient list. Return valid JSON only.",
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=500,
        )
        parsed = parse_json_response(raw)
        matches = []
        for item in parsed.get("matches", []):
            if not isinstance(item, dict):
                continue
            patient_id = int(item.get("patient_id") or 0)
            if not patient_id:
                continue
            matches.append(
                {
                    "patient_id": patient_id,
                    "patient_name": _text(item.get("patient_name"), "Patient"),
                    "summary": _text(item.get("summary"), "Matching record."),
                }
            )
        return {"answer": _text(parsed.get("answer"), "Here is what I found."), "matches": matches[:8]}
    except Exception:
        return _fallback_assistant_search(db, doctor_id, safe_query)
