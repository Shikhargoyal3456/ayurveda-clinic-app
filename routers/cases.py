from datetime import datetime
import ast
import logging
import os
import re
import tempfile
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session, joinedload

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient
from app.portal_auth import normalize_doctor_type
try:
    from app.rag_engine import get_rag_engine
except Exception as exc:
    _rag_import_error = str(exc)

    def get_rag_engine():
        raise RuntimeError(f"RAG engine unavailable: {_rag_import_error}")
from models.prescription import Prescription
from services.ai_provider import generate_role_based_prescription_sync
from services.diet_ai import generate_diet_plan, generate_whatsapp_message
from services.voice_ai import structure_case_sheet, transcribe_audio
from services.whatsapp import build_whatsapp_link
from shared.template_engine import render_template


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["cases"])
logger = logging.getLogger(__name__)
PRESCRIPTION_ORDER_SALT = "prescription-order"


def _load_prescription_order_token(prescription_token: str) -> int:
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=PRESCRIPTION_ORDER_SALT)
    payload = serializer.loads(prescription_token, max_age=60 * 60 * 24 * 30)
    return int(payload["prescription_id"])


def _prescription_medicines_for_order(prescription: Prescription) -> list[dict[str, object]]:
    medicines: list[dict[str, object]] = []
    for medicine in prescription.medicines or []:
        if not isinstance(medicine, dict):
            continue
        name = str(medicine.get("name", "")).strip()
        if not name:
            continue
        medicines.append(
            {
                "name": name,
                "dosage": str(medicine.get("dosage", "")).strip(),
                "frequency": str(medicine.get("frequency", "")).strip(),
                "qty": 1,
            }
        )
    return medicines


def _format_ai_prescription(raw_text: str | None) -> dict[str, object] | None:
    default_payload = {
        "sections": [],
        "sources": [],
        "raw_answer": "",
    }
    if raw_text is None:
        return default_payload

    raw_text = raw_text.strip()
    if not raw_text:
        return default_payload

    heading_map = {
        "Possible Diagnosis": "Diagnosis",
        "Dosha Imbalance": "Treatment",
        "Relevant Herbs": "Medicines",
        "Diet Recommendations": "Diet",
        "Lifestyle Advice": "Lifestyle",
        "Ayurvedic Explanation": "Treatment",
        "Nidana": "Nidana",
        "Samprapti": "Samprapti",
        "Chikitsa": "Chikitsa",
        "Pathya-Apathya": "Pathya-Apathya",
        "Differential Diagnosis": "Differential Diagnosis",
        "Red Flag Symptoms": "Red Flag Symptoms",
        "Investigations Suggested": "Investigations Suggested",
        "First-line Treatment": "First-line Treatment",
        "Patient Counselling": "Patient Counselling",
        "Patient Counseling": "Patient Counselling",
        "Constitutional Analysis": "Constitutional Analysis",
        "Rubric Selection": "Rubric Selection",
        "Remedy Indicated": "Remedy Indicated",
        "Auxiliary Measures": "Auxiliary Measures",
        "Clinical Assessment": "Clinical Assessment",
        "Radiographic Recommendation": "Radiographic Recommendation",
        "Treatment Plan": "Treatment Plan",
        "Patient Instructions": "Patient Instructions",
        "Clinical Reasoning": "Clinical Reasoning",
        "Assessment Findings to Confirm": "Assessment Findings to Confirm",
        "Treatment Protocol": "Treatment Protocol",
        "Home Exercise Program": "Home Exercise Program",
        "Goals and Prognosis": "Goals and Prognosis",
    }

    answer_text, _, sources_text = raw_text.partition("\n\nSources:\n")
    section_order = [
        "Diagnosis",
        "Treatment",
        "Diet",
        "Lifestyle",
        "Medicines",
        "Nidana",
        "Samprapti",
        "Chikitsa",
        "Pathya-Apathya",
        "Differential Diagnosis",
        "Red Flag Symptoms",
        "Investigations Suggested",
        "First-line Treatment",
        "Patient Counselling",
        "Constitutional Analysis",
        "Rubric Selection",
        "Remedy Indicated",
        "Auxiliary Measures",
        "Clinical Assessment",
        "Radiographic Recommendation",
        "Treatment Plan",
        "Patient Instructions",
        "Clinical Reasoning",
        "Assessment Findings to Confirm",
        "Treatment Protocol",
        "Home Exercise Program",
        "Goals and Prognosis",
    ]
    grouped_sections: dict[str, list[str]] = {heading: [] for heading in section_order}
    current_heading: str | None = None

    def _extract_heading_and_body(line: str) -> tuple[str | None, str]:
        stripped = line.strip()
        if not stripped:
            return None, ""
        numbered_match = re.match(r"^\d+\.\s*(.*)$", stripped)
        if numbered_match:
            stripped = numbered_match.group(1).strip()
        if stripped.startswith("**") and ":**" in stripped:
            heading_text, remainder = stripped[2:].split(":**", 1)
            heading = heading_map.get(heading_text.strip())
            return heading, remainder.strip()
        if stripped.startswith("**") and stripped.endswith("**"):
            stripped = stripped[2:-2].strip()
        if ":" in stripped:
            heading_text, remainder = stripped.split(":", 1)
            heading = heading_map.get(heading_text.strip())
            if heading is not None:
                return heading, remainder.strip()
        if stripped.endswith(":"):
            stripped = stripped[:-1].strip()
        if stripped in heading_map:
            return heading_map[stripped], ""
        return None, ""

    for line in answer_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalized_heading, inline_body = _extract_heading_and_body(stripped)
        if normalized_heading is not None:
            current_heading = normalized_heading
            if inline_body:
                grouped_sections[current_heading].append(inline_body)
            continue
        if current_heading in grouped_sections:
            grouped_sections[current_heading].append(stripped)

    sources = [line.strip()[2:] for line in sources_text.splitlines() if line.strip().startswith("- ")] if sources_text else []
    sections = [
        {"heading": heading, "body": "\n".join(lines).strip()}
        for heading in section_order
        for lines in [grouped_sections[heading]]
        if "\n".join(lines).strip()
    ]
    if not any(section["body"] for section in sections) and answer_text.strip():
        sections = [{"heading": "Treatment", "body": answer_text.strip()}]
    return {"sections": sections, "sources": sources, "raw_answer": answer_text.strip()}


def _get_patient_or_404(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = (
        db.query(Patient)
        .options(joinedload(Patient.cases), joinedload(Patient.doctor))
        .filter(Patient.id == patient_id, Patient.doctor_id == doctor_id)
        .first()
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _extract_scanned_medicines(analysis: str) -> list[str]:
    medicines: list[str] = []
    capture = False
    for line in analysis.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if "MEDICINES DETECTED" in upper:
            capture = True
            continue
        if capture and ("MEDICINE DETAILS" in upper or stripped.startswith("---")):
            if medicines:
                break
        if capture:
            cleaned = re.sub(r"^[\-\*\d\.\s]+", "", stripped).strip()
            cleaned = cleaned.replace("**", "").strip("* ")
            if cleaned and "MEDICINES DETECTED" not in cleaned.upper():
                medicines.append(cleaned)
    return medicines[:12]


def _compact_case_value(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalized_ai_mode(value: str | None) -> str:
    cleaned = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in {"ayurveda", "modern", "homeopathy", "physiotherapy", "dentistry", "integrated", "general"}:
        return cleaned
    return ""


def _structured_case_value(value: object) -> str:
    if value is None:
        return ""

    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "None":
            return ""
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            parsed = text

    if isinstance(parsed, dict):
        preferred_keys = [
            "complaint",
            "value",
            "name",
            "chief_complaint",
            "symptoms",
            "notes",
            "diagnosis",
            "duration",
            "severity",
        ]
        for key in preferred_keys:
            if key not in parsed:
                continue
            extracted = _structured_case_value(parsed.get(key))
            if extracted:
                return extracted
        for raw_item in parsed.values():
            extracted = _structured_case_value(raw_item)
            if extracted:
                return extracted
        return ""

    if isinstance(parsed, list):
        values = [_structured_case_value(item) for item in parsed]
        return ", ".join(item for item in values if item)

    # Remove empty structured-note noise like "field: None" or "medicines: []".
    cleaned = str(parsed).strip()
    if not cleaned or cleaned in {"None", "[]", "{}"}:
        return ""
    cleaned = re.sub(r"\b[\w_]+:\s*(None|\[\]|\{\})\b", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _case_query_text(case: CaseSheet) -> str:
    parts = [
        f"Chief complaints and symptoms: {_compact_case_value(_structured_case_value(case.symptoms), 'Not clearly recorded.')}",
        f"Working diagnosis: {_compact_case_value(_structured_case_value(case.diagnosis), 'Not recorded.')}",
        f"Clinical notes: {_compact_case_value(_structured_case_value(case.notes), 'No additional notes.')}",
    ]
    if case.followup_notes:
        parts.append(f"Follow-up considerations: {_compact_case_value(_structured_case_value(case.followup_notes))}")
    return "\n".join(parts)


def _case_ai_payload(case: CaseSheet) -> dict[str, object]:
    patient = case.patient
    doctor = getattr(patient, "doctor", None)
    return {
        "case_id": case.id,
        "patient_name": _compact_case_value(getattr(patient, "name", ""), "Unknown"),
        "age": _compact_case_value(getattr(patient, "age", ""), "Not recorded"),
        "gender": _compact_case_value(getattr(patient, "gender", ""), "Not recorded"),
        "phone": _compact_case_value(getattr(patient, "phone", "")),
        "doctor_name": _compact_case_value(getattr(doctor, "full_name", ""), getattr(doctor, "username", "Doctor")),
        "doctor_specialty": _compact_case_value(getattr(doctor, "specialty", ""), "ayurveda"),
        "prakriti": _structured_case_value(case.prakriti),
        "diagnosis": _structured_case_value(case.diagnosis),
        "symptoms": _structured_case_value(case.symptoms),
        "notes": _structured_case_value(case.notes),
        "followup_notes": _structured_case_value(case.followup_notes),
        "patient_context": _patient_context_text(case),
        "query_text": _case_query_text(case),
    }


def _patient_context_text(case: CaseSheet) -> str:
    patient = case.patient
    return (
        f"Patient name: {_compact_case_value(getattr(patient, 'name', ''), 'Unknown')}.\n"
        f"Age: {_compact_case_value(getattr(patient, 'age', ''), 'Not recorded')}.\n"
        f"Gender: {_compact_case_value(getattr(patient, 'gender', ''), 'Not recorded')}.\n"
        f"Prakriti / constitution: {_compact_case_value(_structured_case_value(case.prakriti), 'Not recorded')}.\n"
        f"Current diagnosis: {_compact_case_value(_structured_case_value(case.diagnosis), 'Not recorded')}.\n"
        f"Symptoms: {_compact_case_value(_structured_case_value(case.symptoms), 'Not clearly recorded')}.\n"
        f"Clinical notes: {_compact_case_value(_structured_case_value(case.notes), 'None')}.\n"
        f"Follow-up plan: {_compact_case_value(_structured_case_value(case.followup_notes), 'None')}."
    )


def _doctor_prescription_mode(request: Request | None, doctor: Doctor | None, override_mode: str | None = None) -> str:
    override = _normalized_ai_mode(override_mode)
    if override:
        return override
    if request is not None:
        session_mode = _normalized_ai_mode(request.session.get("portal_doctor_type"))
        if session_mode:
            return session_mode
    specialty = getattr(doctor, "specialty", None) if doctor is not None else None
    return normalize_doctor_type(None, specialty)


def _answer_needs_retry(answer: object) -> bool:
    text = str(answer or "").strip().lower()
    low_signal_markers = (
        "retrieved context is insufficient",
        "presenting complaints are not provided",
        "patient's current disease",
        "impossible to determine nidana",
        "no clinical reasoning can be applied",
        "symptoms are required before ai analysis can run",
    )
    return any(marker in text for marker in low_signal_markers)


def _build_case_ai_answer(case: CaseSheet, request: Request | None = None, override_mode: str | None = None) -> dict[str, object]:
    doctor = getattr(case.patient, "doctor", None)
    effective_mode = _doctor_prescription_mode(request, doctor, override_mode=override_mode)
    payload = _case_ai_payload(case)
    result = generate_role_based_prescription_sync(payload, effective_mode)
    rendered = str(result.get("rendered_prescription") or "").strip()
    prescription_payload = result.get("prescription")
    if rendered:
        prescription = rendered
    elif isinstance(prescription_payload, dict):
        prescription = json.dumps(prescription_payload, ensure_ascii=False, indent=2)
    else:
        prescription = str(prescription_payload or "").strip()
    references = list(result.get("references", []) or [])
    if not prescription:
        raise RuntimeError("AI prescription response was empty.")
    return {
        "answer": prescription,
        "sources": references,
        "context_passages": list(result.get("context_passages", []) or []),
        "source": str(result.get("provider") or "gemini"),
        "mode": str(result.get("mode") or effective_mode),
        "warning": result.get("warning"),
    }


async def _build_case_diet_payload(case: CaseSheet) -> dict[str, object]:
    patient = case.patient
    diet_plan = await generate_diet_plan(
        {
            "patient_name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone": patient.phone,
            "prakriti": _structured_case_value(case.prakriti),
            "diagnosis": _structured_case_value(case.diagnosis),
            "symptoms": _structured_case_value(case.symptoms),
            "notes": _structured_case_value(case.notes),
            "followup_notes": _structured_case_value(case.followup_notes),
            "doctor_name": _compact_case_value(getattr(case.patient.doctor, "full_name", ""), getattr(case.patient.doctor, "username", "Doctor")),
        }
    )
    whatsapp_message = generate_whatsapp_message(patient.name, diet_plan)
    return {
        "case_id": case.id,
        "diet_plan": diet_plan,
        "diet_view": {
            "plan": _format_diet_plan_view(diet_plan),
            "whatsapp_link": build_whatsapp_link(patient.phone, whatsapp_message),
        },
    }


def _set_case_ai_result(request: Request, key: str, payload: dict[str, object]) -> None:
    request.session[key] = payload


@router.post("/scan-prescription/")
async def scan_prescription(
    prescription_image: UploadFile = File(...),
    phone: str = Form(default=""),
    doctor: Doctor = Depends(get_current_doctor),
):
    _ = doctor
    if not prescription_image.filename:
        return JSONResponse({"success": False, "error": "Prescription image is required."}, status_code=400)

    try:
        image_bytes = await prescription_image.read()
        files = {
            "image": (
                prescription_image.filename,
                image_bytes,
                prescription_image.content_type or "application/octet-stream",
            )
        }
        data = {"phone": phone} if phone else {}

        response = await run_in_threadpool(
            requests.post,
            "http://127.0.0.1:3000/prescriptions/scan",
            files=files,
            data=data,
            timeout=60,
        )
        payload = response.json()
        analysis = str(payload.get("analysis") or payload.get("fullAnalysis") or "")
        payload.setdefault("success", response.ok)
        payload.setdefault("fullAnalysis", analysis)
        payload.setdefault("medicines", _extract_scanned_medicines(analysis))
        return JSONResponse(payload, status_code=response.status_code)
    except requests.exceptions.Timeout:
        return JSONResponse({"success": False, "error": "Scanner timeout. Please try again."}, status_code=504)
    except Exception as exc:
        logger.exception("Prescription scanner proxy failed: %s", exc)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


@router.get("/pharmacy/order/{prescription_token}")
def prescription_medicine_order_page(
    prescription_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        prescription_id = _load_prescription_order_token(prescription_token)
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError) as exc:
        logger.warning("Invalid prescription order token: %s", exc)
        raise HTTPException(status_code=404, detail="Prescription not found") from exc

    prescription = (
        db.query(Prescription)
        .options(joinedload(Prescription.patient))
        .filter(Prescription.id == prescription_id)
        .first()
    )
    if prescription is None or prescription.patient is None:
        raise HTTPException(status_code=404, detail="Prescription not found")

    medicines_json = _prescription_medicines_for_order(prescription)
    return templates.TemplateResponse(
        "patient_order.html",
        {
            "request": request,
            "token": prescription_token,
            "csrf_token": ensure_csrf_token(request),
            "prefill_medicines": medicines_json,
            "prefill_patient": {
                "name": prescription.patient.name,
                "phone": prescription.patient.phone or "",
                "address": prescription.patient.address or "",
            },
            "prefill_order_source": "prescription",
            "prefill_prescription_id": prescription.id,
        },
    )


def _pop_case_ai_result(request: Request, key: str) -> dict[str, object] | None:
    payload = request.session.pop(key, None)
    return payload if isinstance(payload, dict) else None


def _structured_case_defaults(transcript: str, structured_case: dict[str, object]) -> dict[str, str]:
    def _as_text(value: object) -> str:
        if isinstance(value, list):
            return "\n".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return "\n".join(f"{key}: {value[key]}" for key in value if str(value[key]).strip())
        return str(value or "").strip()

    symptoms_parts = [
        _as_text(structured_case.get("chief_complaints")),
        _as_text(structured_case.get("history_of_present_illness")),
    ]
    notes_parts = [
        _as_text(structured_case.get("examination_findings")),
        _as_text(structured_case.get("treatment_plan")),
        _as_text(structured_case.get("follow_up")),
        transcript.strip(),
    ]
    return {
        "prakriti": _as_text(structured_case.get("prakriti")),
        "diagnosis": _as_text(structured_case.get("diagnosis")),
        "symptoms": "\n\n".join(part for part in symptoms_parts if part),
        "notes": "\n\n".join(part for part in notes_parts if part),
        "followup_notes": _as_text(structured_case.get("follow_up")),
    }


def _format_diet_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{key}: {value[key]}" for key in value if str(value[key]).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _format_diet_plan_view(diet_plan: dict[str, object]) -> dict[str, object]:
    return {
        "summary": str(diet_plan.get("diagnosis_summary") or diet_plan.get("summary") or "").strip(),
        "dosha_assessment": str(diet_plan.get("dosha_assessment") or "").strip(),
        "meal_plan": _format_diet_value(diet_plan.get("meal_plan")),
        "foods_to_favor": _format_diet_value(diet_plan.get("foods_to_favor")),
        "foods_to_avoid": _format_diet_value(diet_plan.get("foods_to_avoid")),
        "lifestyle_tips": _format_diet_value(diet_plan.get("lifestyle_tips")),
        "precautions": _format_diet_value(diet_plan.get("precautions")),
    }


@router.get("/patients/{patient_id}/cases/new")
def add_case_page(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _get_patient_or_404(db, doctor.id, patient_id)
    return render_template(templates, request,
        "add_case.html",
        {
            "patient": patient,
            "specialty": patient.doctor.specialty or "ayurveda",
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
            "voice_transcript": "",
            "voice_structured_case": None,
            "prefill_case": {},
        },
    )


@router.post("/patients/{patient_id}/cases/transcribe-audio")
async def transcribe_case_audio(
    patient_id: int,
    request: Request,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _get_patient_or_404(db, doctor.id, patient_id)
    if not audio_file.filename:
        set_flash(request, "Select an audio file before transcribing.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/cases/new", status_code=303)

    suffix = Path(audio_file.filename).suffix or ".wav"
    temp_path = ""
    try:
        form = await request.form()
        handle_fd, temp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(await audio_file.read())
        language = str(form.get("language", "auto"))
        transcript = await run_in_threadpool(transcribe_audio, temp_path, language)
        structured_case = await run_in_threadpool(structure_case_sheet, transcript, patient.name)
        track_event("voice_transcription_used", doctor_id=doctor.id, patient_id=patient.id, mode="upload")
        return render_template(templates, request,
            "add_case.html",
            {
                "patient": patient,
                "specialty": patient.doctor.specialty or "ayurveda",
                "flash": {"category": "success", "message": "Audio transcribed successfully. Review before saving."},
                "csrf_token": ensure_csrf_token(request),
                "voice_transcript": transcript,
                "voice_structured_case": structured_case,
                "prefill_case": _structured_case_defaults(transcript, structured_case),
            },
        )
    except Exception as exc:
        logger.exception("Uploaded audio transcription failed for patient_id=%s: %s", patient.id, exc)
        set_flash(request, "Voice transcription is temporarily unavailable. Please type the case details manually.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/cases/new", status_code=303)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/patients/{patient_id}/cases/transcribe-live")
async def transcribe_live_audio(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    """Accepts raw audio blob from browser microphone and returns transcript as JSON."""
    from fastapi.responses import JSONResponse

    patient = _get_patient_or_404(db, doctor.id, patient_id)

    form = await request.form()
    audio_blob = form.get("audio_blob")
    language = str(form.get("language", "auto"))

    if audio_blob is None:
        return JSONResponse({"error": "No audio received."}, status_code=400)

    suffix = ".webm"
    temp_path = ""
    try:
        import tempfile, os
        handle_fd, temp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(await audio_blob.read())
        transcript = await run_in_threadpool(transcribe_audio, temp_path, language)
        structured_case = await run_in_threadpool(structure_case_sheet, transcript, patient.name)
        prefill = _structured_case_defaults(transcript, structured_case)
        specialty = getattr(patient.doctor, "specialty", "ayurveda")
        track_event("voice_transcription_used", doctor_id=doctor.id, patient_id=patient.id, mode="live")
        return JSONResponse({
            "transcript": transcript,
            "structured_case": structured_case,
            "prefill": prefill,
            "specialty": specialty,
        })
    except Exception as exc:
        logger.exception("Live transcription failed for patient_id=%s: %s", patient.id, exc)
        return JSONResponse({"error": "Voice transcription is temporarily unavailable."}, status_code=503)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.post("/patients/{patient_id}/cases")
def save_case(
    patient_id: int,
    request: Request,
    prakriti: str = Form("", max_length=80),
    diagnosis: str = Form("", max_length=255),
    symptoms: str = Form("", max_length=5000),
    notes: str = Form("", max_length=5000),
    vitals: str = Form(""),
    icd_code: str = Form(""),
    tooth_number: str = Form(""),
    pain_scale: str = Form(""),
    constitution: str = Form(""),
    remedy: str = Form(""),
    procedure: str = Form(""),
    chief_complaint: str = Form(""),
    lab_notes: str = Form(""),
    miasm_notes: str = Form(""),
    rehab_protocol: str = Form(""),
    specialty: str = Form("ayurveda"),
    followup_date: str = Form(""),
    followup_notes: str = Form("", max_length=2000),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _get_patient_or_404(db, doctor.id, patient_id)
    try:
        parsed_followup = datetime.strptime(followup_date, "%Y-%m-%d").date() if followup_date else None
    except ValueError:
        set_flash(request, "Follow-up date must use the YYYY-MM-DD format.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/cases/new", status_code=303)

    valid_specialties = {
        "ayurveda", "modern_medicine", "homeopathy",
        "dental", "physiotherapy"
    }
    if specialty not in valid_specialties:
        specialty = "ayurveda"

    if specialty == "modern_medicine":
        final_symptoms = chief_complaint.strip() or symptoms.strip()
        final_diagnosis = (
            f"{icd_code.strip()} - {diagnosis.strip()}"
            if icd_code.strip() else diagnosis.strip()
        )
        final_prakriti = (
            f"Vitals: {vitals.strip()}" if vitals.strip() else "N/A"
        )
        final_notes = lab_notes.strip() or notes.strip()

    elif specialty == "homeopathy":
        final_symptoms = chief_complaint.strip() or symptoms.strip()
        final_diagnosis = remedy.strip() or diagnosis.strip()
        final_prakriti = constitution.strip() or prakriti.strip()
        final_notes = miasm_notes.strip() or notes.strip()

    elif specialty == "dental":
        final_symptoms = chief_complaint.strip() or symptoms.strip()
        final_diagnosis = procedure.strip() or diagnosis.strip()
        final_prakriti = (
            f"Tooth {tooth_number.strip()}"
            if tooth_number.strip() else prakriti.strip()
        )
        final_notes = notes.strip()

    elif specialty == "physiotherapy":
        final_symptoms = symptoms.strip()
        final_diagnosis = diagnosis.strip()
        final_prakriti = (
            f"Pain {pain_scale.strip()}/10"
            if pain_scale.strip() else prakriti.strip()
        )
        final_notes = rehab_protocol.strip() or notes.strip()

    else:
        final_symptoms = symptoms.strip()
        final_diagnosis = diagnosis.strip()
        final_prakriti = prakriti.strip()
        final_notes = notes.strip()

    case = CaseSheet(
        patient_id=patient.id,
        prakriti=final_prakriti,
        diagnosis=final_diagnosis,
        symptoms=final_symptoms,
        notes=final_notes,
        followup_date=parsed_followup,
        followup_notes=followup_notes.strip() or None,
    )
    db.add(case)
    commit_with_retry(db)
    write_audit_event("case_created", request, case_id=case.id, patient_id=patient.id, diagnosis=case.diagnosis)
    track_event("case_sheet_saved", doctor_id=doctor.id, patient_id=patient.id, case_id=case.id)
    set_flash(request, "Case sheet saved.", "success")
    return RedirectResponse(url=f"/patients/{patient.id}/cases", status_code=303)


@router.get("/patients/{patient_id}/cases")
def view_cases(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _get_patient_or_404(db, doctor.id, patient_id)
    diet_result = _pop_case_ai_result(request, "_diet_plan_result")
    cases = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient.id)
        .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
        .limit(100)
        .all()
    )
    cases_with_ai = [
        {
            "record": case,
            "ai_view": _format_ai_prescription(case.ai_prescription) if case.ai_prescription else None,
            "diet_view": (
                {
                    "plan": _format_diet_plan_view(diet_result.get("diet_plan", {})),
                    "whatsapp_link": str(diet_result.get("whatsapp_link", "")).strip(),
                }
                if diet_result and int(diet_result.get("case_id", 0)) == case.id
                else None
            ),
        }
        for case in cases
    ]
    return render_template(templates, request,
        "view_cases.html",
        {
            "patient": patient,
            "cases": cases_with_ai,
            "current_doctor_type": _doctor_prescription_mode(request, doctor),
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/cases/{case_id}/generate-ai")
def generate_ai_prescription(
    case_id: int,
    request: Request,
    mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    case = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(CaseSheet.id == case_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    try:
        rag_result = _build_case_ai_answer(case, request=request, override_mode=mode)
    except Exception as exc:
        logger.exception("AI prescription generation failed for case_id=%s: %s", case.id, exc)
        set_flash(
            request,
            f"AI prescription generation failed: {exc}",
            "danger",
        )
        return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)
    sources = rag_result.get("sources", [])
    source_block = "\n\nSources:\n" + "\n".join(f"- {source}" for source in sources) if sources else ""
    case.ai_prescription = f"{rag_result['answer']}{source_block}"
    commit_with_retry(db)
    write_audit_event("ai_prescription_generated", request, case_id=case.id, patient_id=case.patient_id)
    track_event("ai_prescription_generated", doctor_id=doctor.id, patient_id=case.patient_id, case_id=case.id)
    set_flash(request, "AI prescription generated.", "success")
    return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)


@router.post("/cases/{case_id}/generate-diet")
async def generate_case_diet_plan(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    case = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(CaseSheet.id == case_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    try:
        payload = await _build_case_diet_payload(case)
        diet_plan = payload["diet_plan"]
        _set_case_ai_result(request, "_diet_plan_result", payload)
        set_flash(request, "AI diet plan generated.", "success")
    except Exception as exc:
        logger.exception("Diet plan generation failed for case_id=%s: %s", case.id, exc)
        set_flash(request, f"Diet AI request failed: {exc}", "danger")
    else:
        track_event("diet_plan_generated", doctor_id=doctor.id, patient_id=case.patient_id, case_id=case.id)
    return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)


@router.post("/api/cases/{case_id}/generate-ai")
def generate_ai_prescription_json(
    case_id: int,
    request: Request,
    mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    case = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(CaseSheet.id == case_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        rag_result = _build_case_ai_answer(case, request=request, override_mode=mode)
    except Exception as exc:
        logger.exception("AI prescription generation failed for case_id=%s: %s", case.id, exc)
        return JSONResponse({"success": False, "error": str(exc), "source": "ai_error"}, status_code=503)
    sources = rag_result.get("sources", [])
    source_block = "\n\nSources:\n" + "\n".join(f"- {source}" for source in sources) if sources else ""
    case.ai_prescription = f"{rag_result['answer']}{source_block}"
    commit_with_retry(db)
    ai_view = _format_ai_prescription(case.ai_prescription)
    return JSONResponse({"success": True, "ai_view": ai_view})


@router.post("/api/cases/{case_id}/generate-diet")
async def generate_case_diet_plan_json(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    case = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(CaseSheet.id == case_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        payload = await _build_case_diet_payload(case)
    except Exception as exc:
        logger.exception("Diet plan generation failed for case_id=%s: %s", case.id, exc)
        return JSONResponse({"success": False, "error": str(exc), "source": "ai_error"}, status_code=503)
    return JSONResponse({"success": True, "diet_view": payload["diet_view"]})
