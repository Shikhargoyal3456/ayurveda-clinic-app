import logging
import json
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import (
    _RATE_LIMIT_BUCKETS,
    _apply_rate_limit,
    ensure_csrf_token,
    get_current_doctor,
    pop_flash,
    rate_limit_dependency,
    verify_csrf,
)
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient
from models.prescription import AIFeedback, Prescription
from app.portal_auth import get_portal_user, normalize_doctor_type
try:
    from app.rag_engine import get_rag_engine
except Exception as exc:
    _rag_import_error = str(exc)

    def get_rag_engine():
        raise RuntimeError(f"RAG engine unavailable: {_rag_import_error}")

try:
    from services.ai_provider import (
        GEMINI_API_KEY,
        GEMINI_MODEL,
        GROQ_API_KEY,
        GROQ_MODEL,
        generate_role_based_prescription,
        get_ai_response,
    )
except Exception as exc:
    _ai_provider_import_error = str(exc)
    GEMINI_API_KEY = ""
    GEMINI_MODEL = settings.gemini_model
    GROQ_API_KEY = ""
    GROQ_MODEL = ""
    def get_ai_response(prompt: str, mode: str = "samhita", context: dict | None = None):
        raise RuntimeError(f"AI provider unavailable: {_ai_provider_import_error}")
    async def generate_role_based_prescription(case_data: dict[str, object], mode: str):
        raise RuntimeError(f"AI provider unavailable: {_ai_provider_import_error}")
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)
from routers.cases import _case_ai_payload, _case_query_text, _patient_context_text


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["ai"])
logger = logging.getLogger(__name__)
rebuild_status = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_error": None,
    "progress_message": "idle",
}
_rebuild_status_lock = Lock()
_AI_RATE_LIMIT_BUCKETS = _RATE_LIMIT_BUCKETS
_AI_EMERGENCY_KEYWORDS = ["chest pain", "bleeding", "unconscious"]


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _ensure_ai_feature_access(request: Request, db: Session) -> dict[str, object]:
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        return {"source": "portal", "user": portal_user}

    doctor_id = request.session.get("doctor_id")
    if doctor_id:
        doctor = db.get(Doctor, int(doctor_id))
        if doctor is not None:
            return {"source": "doctor", "user": doctor}

    raise HTTPException(status_code=303, headers={"Location": "/login"})


def _wrap_ai_safety_response(symptoms: str, result: dict[str, object]) -> dict[str, object]:
    try:
        answer = str(result.get("answer", "") or "")
        prefixes = ["This is advisory. Doctor review required."]
        symptom_text = symptoms.lower()
        if any(keyword in symptom_text for keyword in _AI_EMERGENCY_KEYWORDS):
            prefixes.insert(0, "Emergency: Seek immediate medical help.")
        result["answer"] = "\n\n".join([*prefixes, answer]).strip()
    except Exception as exc:  # pragma: no cover
        logger.exception("AI safety wrapper failed: %s", exc)
    return result


def _extract_case_text_safely(case: CaseSheet) -> str:
    return f"{_patient_context_text(case)}\n\n{_case_query_text(case)}".strip()


def _active_doctor_mode(request: Request, doctor: Doctor, override_mode: str | None = None) -> str:
    cleaned = str(override_mode or "").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in {"ayurveda", "modern", "homeopathy", "physiotherapy", "dentistry", "integrated", "general"}:
        return cleaned
    session_mode = str(request.session.get("portal_doctor_type") or "").strip()
    if session_mode:
        return normalize_doctor_type(session_mode)
    return normalize_doctor_type(None, getattr(doctor, "specialty", None))


async def _extract_analysis_payload(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
        return {
            "symptoms": str((payload or {}).get("symptoms", "")).strip(),
            "mode": str((payload or {}).get("mode", "samhita")).strip().lower() or "samhita",
        }

    form = await request.form()
    return {
        "symptoms": str(form.get("symptoms", "")).strip(),
        "mode": str(form.get("mode", "samhita")).strip().lower() or "samhita",
    }


async def _ai_rate_limit(request: Request, doctor: Doctor = Depends(get_current_doctor)) -> None:
    key = f"ai:{doctor.id}:{request.session.get('doctor_id', 'session')}"
    retry_after_seconds = _apply_rate_limit(key, limit=10, window_seconds=60)
    if retry_after_seconds is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many AI analysis requests. Please wait and try again.",
            headers={"Retry-After": str(retry_after_seconds)},
        )


@router.get("/ai-analyzer")
def ai_analyzer_page(request: Request, _: Doctor = Depends(get_current_doctor)):
    return templates.TemplateResponse(
        request,
        "ai_analyzer.html",
        {"request": request, "flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/api/ai/analyze")
async def analyze_symptoms(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
    ____: None = Depends(_ai_rate_limit),
    __: None = Depends(rate_limit_dependency("ai-analyze", limit=12, window_seconds=60)),
    ___: None = Depends(verify_csrf),
):
    access = check_subscription_access(doctor, "ai_call")
    logger.info("Subscription check: user=%s, feature=ai_call, allowed=%s", doctor.id, access["allowed"])
    if not access["allowed"]:
        return JSONResponse(build_paywall_response(doctor, "ai_call"), status_code=403)
    payload = await _extract_analysis_payload(request)
    symptoms = payload.get("symptoms", "")
    mode = payload.get("mode", "samhita")
    if not symptoms:
        raise HTTPException(status_code=400, detail="Symptoms are required.")
    if len(symptoms) > 2000:
        raise HTTPException(status_code=400, detail="Symptoms must be 2000 characters or fewer.")

    logger.info("AI analyzer request received: symptom_length=%s", len(symptoms))
    try:
        sources: list[str] = []
        context_passages: list[str] = []
        if mode == "samhita":
            try:
                passages = await run_in_threadpool(get_rag_engine().retrieve, symptoms, 3)
            except Exception as retrieval_exc:
                logger.warning("Samhita retrieval degraded for AI analyzer: %s", retrieval_exc)
                passages = []
            sources = [str(item.source_file) for item in passages]
            context_passages = [str(item.text).strip() for item in passages]
            result = await run_in_threadpool(
                get_ai_response,
                symptoms,
                "samhita",
                {
                    "doctor_id": getattr(doctor, "id", None),
                    "specialty": getattr(doctor, "specialty", ""),
                    "sources": sources,
                    "context_passages": context_passages,
                },
            )
        else:
            result = await run_in_threadpool(
                get_ai_response,
                symptoms,
                mode,
                {"doctor_id": getattr(doctor, "id", None), "specialty": getattr(doctor, "specialty", "")},
            )
        result.setdefault("sources", sources)
        result.setdefault("context_passages", context_passages)
    except Exception as exc:
        logger.exception("AI analyzer failed unexpectedly: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    write_audit_event("ai_analyzer_used", request, symptom_length=len(symptoms), source_count=len(result.get("sources", [])))
    result["mode"] = str(result.get("mode") or mode)
    track_event("ai_analyzer_used", doctor_id=request.session.get("doctor_id"), mode=result.get("mode", "unknown"))
    increment_usage(doctor, "ai_call")
    result = _wrap_ai_safety_response(symptoms, result)
    return JSONResponse(result)


@router.post("/api/ai/medicine-info")
async def get_medicine_info(
    request: Request,
    payload: dict[str, object] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    _ensure_ai_feature_access(request, db)
    medicine_name = str(payload.get("medicine_name") or "").strip()
    if not medicine_name:
        raise HTTPException(status_code=400, detail="medicine_name is required.")

    from services.medicine_info_ai import get_medicine_info_pure_ai

    try:
        info = await get_medicine_info_pure_ai(
            medicine_name,
            {
                "diagnosis": str(payload.get("diagnosis") or "").strip(),
                "symptoms": str(payload.get("symptoms") or "").strip(),
                "age": payload.get("age"),
            },
        )
    except Exception as exc:
        logger.exception("AI medicine info failed for %s: %s", medicine_name, exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service temporarily unavailable",
                "message": "Unable to generate medicine information. Please try again.",
                "source": "ai_unavailable",
            },
        ) from exc
    return JSONResponse({"success": True, "source": "ai", "data": info})


@router.post("/api/ai/medicine-info/pure")
async def get_medicine_info_pure(
    request: Request,
    payload: dict[str, object] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    _ensure_ai_feature_access(request, db)
    medicine_name = str(payload.get("medicine_name") or "").strip()
    if not medicine_name:
        raise HTTPException(status_code=400, detail="medicine_name is required.")

    from services.medicine_info_ai import get_medicine_info_pure_ai

    try:
        info = await get_medicine_info_pure_ai(
            medicine_name,
            {
                "diagnosis": str(payload.get("diagnosis") or "").strip(),
                "symptoms": str(payload.get("symptoms") or "").strip(),
                "age": payload.get("age"),
            },
        )
        return JSONResponse({"success": True, "source": "ai", "data": info})
    except Exception as exc:
        logger.exception("Pure AI medicine info failed for %s: %s", medicine_name, exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service temporarily unavailable",
                "message": "Unable to generate medicine information. Please try again.",
                "source": "ai_unavailable",
            },
        ) from exc


@router.post("/api/ai/prescription/enhance")
async def enhance_prescription_with_details(
    request: Request,
    payload: dict[str, object] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    _ensure_ai_feature_access(request, db)

    from services.medicine_info_ai import get_prescription_with_details

    try:
        enhanced = await get_prescription_with_details(payload)
    except Exception as exc:
        logger.exception("AI prescription enhancement failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service temporarily unavailable",
                "message": "Unable to enhance prescription details. Please try again.",
                "source": "ai_unavailable",
            },
        ) from exc
    return JSONResponse(enhanced)


@router.post("/api/ai/prescription/{case_id}")
async def generate_ai_prescription(
    case_id: int,
    request: Request,
    mode: str | None = None,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    ____: None = Depends(_ai_rate_limit),
    __: None = Depends(rate_limit_dependency("ai-prescription", limit=12, window_seconds=60)),
    ___: None = Depends(verify_csrf),
):
    access = check_subscription_access(doctor, "ai_call")
    if not access["allowed"]:
        return JSONResponse(build_paywall_response(doctor, "ai_call"), status_code=403)

    case = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(CaseSheet.id == case_id, Patient.doctor_id == doctor.id)
        .first()
    )
    if case is None:
        return JSONResponse({"success": False, "error": "Case not found"}, status_code=404)

    try:
        effective_mode = _active_doctor_mode(request, doctor, override_mode=mode)
        case_data = _case_ai_payload(case)
        case_data["requested_mode"] = effective_mode
        result = await generate_role_based_prescription(case_data, effective_mode)
        write_audit_event("ai_case_prescription_generated", request, case_id=case.id, patient_id=case.patient_id)
        track_event("ai_case_prescription_generated", doctor_id=doctor.id, patient_id=case.patient_id, case_id=case.id)
        increment_usage(doctor, "ai_call")
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("AI prescription endpoint failed for case_id=%s: %s", case_id, exc)
        return JSONResponse(
            {"success": False, "error": str(exc), "source": "ai_error"},
            status_code=503,
        )


@router.post("/api/ai/stream")
async def stream_ai_response(
    payload: dict[str, object] = Body(...),
    doctor: Doctor = Depends(get_current_doctor),
    __: None = Depends(rate_limit_dependency("ai-stream", limit=20, window_seconds=60)),
):
    del doctor
    prompt = str(payload.get("prompt", "") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")

    from services.ai_provider import stream_with_gemini

    def generate():
        try:
            for chunk in stream_with_gemini(
                "You are a careful healthcare AI assistant. Be concise, practical, and safe.",
                prompt,
                temperature=0.2,
                max_output_tokens=1600,
            ):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _background_rebuild_knowledge() -> None:
    with _rebuild_status_lock:
        rebuild_status["running"] = True
        rebuild_status["last_started"] = datetime.now(timezone.utc).isoformat()
        rebuild_status["last_error"] = None
        rebuild_status["progress_message"] = "rebuild_started"
    logger.info("Knowledge rebuild started")
    try:
        with _rebuild_status_lock:
            rebuild_status["progress_message"] = "building_vector_store"
        report = get_rag_engine().prepare(force_rebuild=True)
        write_audit_event("knowledge_rebuilt", None, chunks=report.get("chunks"), rebuilt=report.get("rebuilt"))
        logger.info(
            "Knowledge rebuild finished: chunks=%s rebuilt=%s",
            report.get("chunks"),
            report.get("rebuilt"),
        )
        with _rebuild_status_lock:
            rebuild_status["progress_message"] = "completed"
    except FileNotFoundError:
        with _rebuild_status_lock:
            rebuild_status["last_error"] = "Source PDFs were missing."
            rebuild_status["progress_message"] = "missing_source_pdfs"
        logger.warning("Knowledge rebuild skipped because source PDFs were missing.")
    except Exception as exc:  # pragma: no cover
        with _rebuild_status_lock:
            rebuild_status["last_error"] = str(exc)
            rebuild_status["progress_message"] = "failed"
        logger.exception("Knowledge rebuild failed in background: %s", exc)
    finally:
        with _rebuild_status_lock:
            rebuild_status["running"] = False
            rebuild_status["last_finished"] = datetime.now(timezone.utc).isoformat()


@router.post("/api/ai/rebuild-knowledge")
def rebuild_knowledge(
    background_tasks: BackgroundTasks,
    _: Doctor = Depends(get_current_doctor),
    __: None = Depends(rate_limit_dependency("knowledge-rebuild", limit=3, window_seconds=300)),
    ___: None = Depends(verify_csrf),
):
    if not settings.samhita_pdfs_dir.exists():
        raise HTTPException(status_code=400, detail=f"PDF directory not found at {settings.samhita_pdfs_dir}")

    with _rebuild_status_lock:
        if rebuild_status["running"] or rebuild_status["progress_message"] == "queued":
            return JSONResponse({"message": "Knowledge rebuild is already in progress."}, status_code=409)
        logger.info("Knowledge rebuild queued by authenticated user")
        rebuild_status["progress_message"] = "queued"
    background_tasks.add_task(_background_rebuild_knowledge)
    return JSONResponse({"message": "Knowledge rebuild started in the background."})


@router.get("/api/ai/rebuild-status")
def get_rebuild_status(_: Doctor = Depends(get_current_doctor)):
    with _rebuild_status_lock:
        return JSONResponse(dict(rebuild_status))


@router.get("/api/ai/status")
@router.get("/ai/status")
def ai_status():
    try:
        engine = get_rag_engine()
    except Exception as exc:
        logger.exception("AI status degraded because RAG engine is unavailable: %s", exc)
        return JSONResponse(
            {
                "gemini": {
                    "configured": bool(GEMINI_API_KEY),
                    "model": GEMINI_MODEL,
                },
                "groq": {
                    "configured": bool(GROQ_API_KEY),
                    "enabled": bool(GROQ_API_KEY),
                    "model": GROQ_MODEL,
                },
                "ollama": {
                    "reachable": False,
                    "enabled": False,
                    "model": None,
                    "host": None,
                },
                "rag_engine": {
                    "mode": "unavailable",
                    "warning": str(exc),
                    "model": None,
                    "provider": "unavailable",
                },
                "active_strategy": "unavailable",
            }
        )
    gemini_configured = bool(GEMINI_API_KEY)
    groq_configured = bool(GROQ_API_KEY)
    gemini_status = engine.gemini_status()
    rag_mode = "gemini" if gemini_configured else ("groq" if groq_configured else "fallback")
    rag_warning = None if gemini_configured or groq_configured else "No remote AI provider is configured."
    rag_provider = "gemini" if gemini_configured else ("groq" if groq_configured else "fallback")
    active_strategy = (
        "gemini_primary_groq_fallback"
        if gemini_configured and groq_configured
        else ("gemini_only" if gemini_configured else ("groq_only" if groq_configured else "fallback_only"))
    )

    return JSONResponse(
        {
            "gemini": {
                "configured": gemini_configured,
                "model": GEMINI_MODEL,
            },
            "groq": {
                "configured": groq_configured,
                "enabled": groq_configured,
                "model": GROQ_MODEL,
            },
            "ollama": {
                "reachable": False,
                "enabled": False,
                "model": None,
                "host": None,
            },
            "rag_engine": {
                "mode": rag_mode,
                "warning": rag_warning,
                "model": gemini_status.get("model") if gemini_configured else (GROQ_MODEL if groq_configured else None),
                "provider": rag_provider,
            },
            "active_strategy": active_strategy,
        }
    )


@router.post("/api/ai/prescription-feedback")
def prescription_feedback(
    request: Request,
    payload: dict[str, object] = Body(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    """
    Collect doctor feedback on AI prescriptions.
    Stored only in the local database.
    """
    rating = int(payload.get("rating", 0) or 0)
    accepted = _coerce_bool(payload.get("accepted"))
    doctor_notes = str(payload.get("doctor_notes") or "").strip() or None
    prescription_id = payload.get("prescription_id")
    case_id = payload.get("case_id")

    if not (1 <= rating <= 5):
        return JSONResponse({"success": False, "error": "Rating must be between 1 and 5"}, status_code=400)
    if prescription_id is None and case_id is None:
        return JSONResponse({"success": False, "error": "prescription_id or case_id is required"}, status_code=400)

    if prescription_id is not None:
        prescription = (
            db.query(Prescription)
            .filter(Prescription.id == int(prescription_id), Prescription.doctor_id == doctor.id)
            .first()
        )
        if prescription is None:
            return JSONResponse({"success": False, "error": "Prescription not found"}, status_code=404)
        prescription.ai_rating = rating
        prescription.ai_accepted = accepted
        prescription.ai_feedback = doctor_notes
        prescription.feedback_updated_at = datetime.now(timezone.utc)

    if case_id is not None:
        case = (
            db.query(CaseSheet)
            .join(Patient)
            .filter(CaseSheet.id == int(case_id), Patient.doctor_id == doctor.id)
            .first()
        )
        if case is None:
            return JSONResponse({"success": False, "error": "Case not found"}, status_code=404)

    db.add(
        AIFeedback(
            prescription_id=int(prescription_id) if prescription_id is not None else None,
            case_id=int(case_id) if case_id is not None else None,
            doctor_id=doctor.id,
            rating=rating,
            accepted=accepted,
            notes=doctor_notes,
        )
    )
    commit_with_retry(db)
    write_audit_event(
        "ai_prescription_feedback_saved",
        request,
        doctor_id=doctor.id,
        prescription_id=int(prescription_id) if prescription_id is not None else None,
        case_id=int(case_id) if case_id is not None else None,
        rating=rating,
        accepted=accepted,
    )
    return {"success": True, "message": "Feedback saved"}
