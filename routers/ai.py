import logging
import time
from threading import Lock
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, rate_limit_dependency, verify_csrf
from app.config import settings
from app.models import Doctor
from app.rag_engine import get_rag_engine
from services.ai_provider import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL
from utils.subscription_utils import (
    build_paywall_response,
    check_subscription_access,
    increment_subscription_usage as increment_usage,
)


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
_AI_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


async def _extract_symptoms(request: Request) -> str:
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc
        return str((payload or {}).get("symptoms", "")).strip()

    form = await request.form()
    return str(form.get("symptoms", "")).strip()


async def _ai_rate_limit(request: Request, doctor: Doctor = Depends(get_current_doctor)) -> None:
    now = time.time()
    key = f"ai:{doctor.id}:{request.session.get('doctor_id', 'session')}"
    entries = _AI_RATE_LIMIT_BUCKETS[key]
    while entries and now - entries[0] > 60:
        entries.popleft()
    if len(entries) >= 10:
        raise HTTPException(status_code=429, detail="Too many AI analysis requests. Please wait and try again.")
    entries.append(now)


@router.get("/ai-analyzer")
def ai_analyzer_page(request: Request, _: Doctor = Depends(get_current_doctor)):
    return templates.TemplateResponse(
        request,
        "ai_analyzer.html",
        {"flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)},
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
    symptoms = await _extract_symptoms(request)
    if not symptoms:
        raise HTTPException(status_code=400, detail="Symptoms are required.")
    if len(symptoms) > 2000:
        raise HTTPException(status_code=400, detail="Symptoms must be 2000 characters or fewer.")

    logger.info("AI analyzer request received: symptom_length=%s", len(symptoms))
    try:
        result = await run_in_threadpool(get_rag_engine().generate_clinical_response, symptoms)
    except Exception as exc:  # pragma: no cover
        logger.exception("AI analyzer failed unexpectedly: %s", exc)
        result = {
            "answer": (
                "AI analysis is temporarily unavailable right now. "
                "Please retry in a moment or continue the consultation without AI assistance."
            ),
            "sources": [],
            "context_passages": [],
            "mode": "error",
            "warning": "Primary AI pipeline failed unexpectedly.",
        }
    write_audit_event("ai_analyzer_used", request, symptom_length=len(symptoms), source_count=len(result.get("sources", [])))
    track_event("ai_analyzer_used", doctor_id=request.session.get("doctor_id"), mode=result.get("mode", "unknown"))
    if result.get("mode") != "error":
        increment_usage(doctor, "ai_call")
    return JSONResponse(result)


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
    engine = get_rag_engine()
    groq_configured = bool(GROQ_API_KEY)
    gemini_configured = bool(GEMINI_API_KEY)
    gemini_status = engine.gemini_status()
    ollama_status = engine.ollama_status(timeout_seconds=2, allow_retries=False)

    if settings.is_testing:
        rag_mode = ollama_status.get("mode", "fallback")
        rag_warning = ollama_status.get("warning")
        rag_provider = ollama_status.get("provider")
        active_strategy = "groq_configured_rag_fallback" if groq_configured else "fallback_only"
    else:
        rag_mode = "gemini" if gemini_configured else "fallback"
        rag_warning = None if gemini_configured else "Gemini API key not configured."
        rag_provider = "gemini" if gemini_configured else "fallback"
        active_strategy = "gemini_rag" if gemini_configured else "fallback"

    return JSONResponse(
        {
            "gemini": {
                "configured": gemini_configured,
                "model": GEMINI_MODEL,
            },
            "groq": {
                "configured": groq_configured,
                "model": GROQ_MODEL,
            },
            "ollama": {
                "reachable": ollama_status.get("available"),
                "model": ollama_status.get("model", settings.ollama_model),
                "host": ollama_status.get("url", settings.ollama_api_url),
            },
            "rag_engine": {
                "mode": rag_mode,
                "warning": rag_warning,
                "model": gemini_status.get("model") if gemini_configured and not settings.is_testing else ollama_status.get("model"),
                "provider": rag_provider,
            },
            "active_strategy": active_strategy,
        }
    )
