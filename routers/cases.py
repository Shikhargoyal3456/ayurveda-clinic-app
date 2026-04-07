from datetime import datetime
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient
from app.rag_engine import get_rag_engine
from services.diet_ai import generate_diet_plan, generate_whatsapp_message
from services.voice_ai import structure_case_sheet, transcribe_audio
from services.whatsapp import build_whatsapp_link


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["cases"])


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
    }

    answer_text, _, sources_text = raw_text.partition("\n\nSources:\n")
    grouped_sections: dict[str, list[str]] = {
        "Diagnosis": [],
        "Treatment": [],
        "Diet": [],
        "Lifestyle": [],
        "Medicines": [],
    }
    current_heading: str | None = None

    for line in answer_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":"):
            current_heading = heading_map.get(stripped[:-1], stripped[:-1])
            continue
        if current_heading in grouped_sections:
            grouped_sections[current_heading].append(stripped)

    sources = [line.strip()[2:] for line in sources_text.splitlines() if line.strip().startswith("- ")] if sources_text else []
    section_order = ["Diagnosis", "Treatment", "Diet", "Lifestyle", "Medicines"]
    sections = [
        {"heading": heading, "body": "\n".join(lines).strip()}
        for heading in section_order
        for lines in [grouped_sections[heading]]
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


def _set_case_ai_result(request: Request, key: str, payload: dict[str, object]) -> None:
    request.session[key] = payload


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
    return templates.TemplateResponse(
        request,
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
        transcript = transcribe_audio(temp_path, language=language)
        structured_case = structure_case_sheet(transcript, patient.name)
        return templates.TemplateResponse(
            request,
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
    except Exception:
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
        transcript = transcribe_audio(temp_path, language=language)
        structured_case = structure_case_sheet(transcript, patient.name)
        prefill = _structured_case_defaults(transcript, structured_case)
        specialty = getattr(patient.doctor, "specialty", "ayurveda")
        return JSONResponse({
            "transcript": transcript,
            "structured_case": structured_case,
            "prefill": prefill,
            "specialty": specialty,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
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
    cases = sorted(patient.cases, key=lambda item: item.created_at, reverse=True)
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
    return templates.TemplateResponse(
        request,
        "view_cases.html",
        {
            "patient": patient,
            "cases": cases_with_ai,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/cases/{case_id}/generate-ai")
def generate_ai_prescription(
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

    patient_context = (
        f"Patient prakriti: {case.prakriti}. Current diagnosis: {case.diagnosis}. Notes: {case.notes or 'None'}."
    )
    try:
        specialty = getattr(case.patient.doctor, "specialty", "ayurveda")
        rag_result = get_rag_engine().generate_clinical_response(
            case.symptoms,
            patient_context=patient_context,
            specialty=specialty,
        )
    except Exception:
        set_flash(
            request,
            "AI prescription generation is temporarily unavailable. The case was kept safely without AI output.",
            "danger",
        )
        return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)
    sources = rag_result.get("sources", [])
    source_block = "\n\nSources:\n" + "\n".join(f"- {source}" for source in sources) if sources else ""
    case.ai_prescription = f"{rag_result['answer']}{source_block}"
    commit_with_retry(db)
    write_audit_event("ai_prescription_generated", request, case_id=case.id, patient_id=case.patient_id)
    set_flash(request, "AI prescription generated.", "success")
    return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)


@router.post("/cases/{case_id}/generate-diet")
def generate_case_diet_plan(
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

    patient = case.patient
    patient_data = {
        "patient_name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone,
        "prakriti": case.prakriti,
        "diagnosis": case.diagnosis,
        "symptoms": case.symptoms,
        "notes": case.notes,
        "followup_notes": case.followup_notes,
    }
    try:
        diet_plan = generate_diet_plan(patient_data)
        whatsapp_message = generate_whatsapp_message(patient.name, diet_plan)
        _set_case_ai_result(
            request,
            "_diet_plan_result",
            {
                "case_id": case.id,
                "diet_plan": diet_plan,
                "whatsapp_link": build_whatsapp_link(patient.phone, whatsapp_message),
            },
        )
        set_flash(request, "AI diet plan generated.", "success")
    except Exception:
        set_flash(request, "Diet AI is temporarily unavailable for this case.", "danger")
    return RedirectResponse(url=f"/patients/{case.patient_id}/cases", status_code=303)
