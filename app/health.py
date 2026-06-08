from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.ai_fallback import fallback_health_status
from app.config import settings
from app.database import engine
from app.runtime import request_load_controller
from services.ai_provider import GROQ_API_KEY
from services.cache_service import redis_health_status
from services.whatsapp import whatsapp_health_status


def database_health() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def ai_health() -> dict[str, Any]:
    fallback = fallback_health_status(probe_remote=False)
    gemini_configured = bool(settings.vertex_ai_project)
    groq_configured = bool(GROQ_API_KEY)
    primary_provider = "gemini" if gemini_configured else ("groq" if groq_configured else "none")
    ai_available = gemini_configured or groq_configured
    status_message = (
        "Vertex AI Gemini is configured as the primary AI provider."
        if gemini_configured
        else ("Groq is configured as the AI provider." if groq_configured else "No remote AI provider is configured.")
    )
    return {
        "status": "ok" if ai_available else "degraded",
        "available": ai_available,
        "fallback_mode": not ai_available,
        "message": status_message,
        "primary_provider": primary_provider,
        "gemini_configured": gemini_configured,
        "groq_configured": groq_configured,
        "ollama_reachable": False,
        "fallback": fallback,
    }


def rag_health() -> dict[str, Any]:
    try:
        docs_path = settings.vector_store_dir / "docs.pkl"
        faiss_path = settings.vector_store_dir / "index.faiss"
        return {
            "status": "ok" if docs_path.exists() and faiss_path.exists() else "degraded",
            "docs_indexed": docs_path.exists(),
            "faiss_index_ready": faiss_path.exists(),
            "vector_store_dir": str(settings.vector_store_dir),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "docs_indexed": False,
            "faiss_index_ready": False,
            "vector_store_dir": str(settings.vector_store_dir),
            "error": str(exc),
        }


def disk_health(path: Path | None = None) -> dict[str, Any]:
    usage = shutil.disk_usage(path or settings.base_dir)
    return {
        "status": "ok",
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
    }


def memory_health() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "status": "ok",
            "rss_bytes": memory_info.rss,
            "vms_bytes": memory_info.vms,
        }
    except Exception as exc:
        return {"status": "unknown", "error": str(exc)}


def analytics_health() -> dict[str, Any]:
    try:
        from services.analytics_service import get_error_summary, load_events

        load_events()
        recent_window_hours = 24
        recent_error_summary = get_error_summary(recent_hours=recent_window_hours)
        lifetime_error_summary = get_error_summary()
        return {
            "status": "working",
            "errors_logged": int(recent_error_summary.get("total_errors") or 0),
            "errors_logged_window_hours": recent_window_hours,
            "errors_logged_lifetime": int(lifetime_error_summary.get("total_errors") or 0),
            "errors_by_type": recent_error_summary.get("errors_by_type") or {},
            "errors_by_route": recent_error_summary.get("errors_by_route") or {},
        }
    except Exception as exc:
        return {"status": "degraded", "errors_logged": 0, "error": str(exc)}


def build_health_report() -> dict[str, Any]:
    database = database_health()
    ai = ai_health()
    rag = rag_health()
    whatsapp = whatsapp_health_status()
    disk = disk_health()
    memory = memory_health()
    analytics = analytics_health()
    redis = redis_health_status()
    runtime_load = request_load_controller.snapshot()
    overall = "ok"
    if any(item.get("status") == "error" for item in (database, ai, rag, disk)):
        overall = "degraded"
    return {
        "status": overall,
        "api": "ok",
        "version": settings.app_version,
        "database": database["status"],
        "ai": ai["status"],
        "ai_readiness": "working" if ai["status"] == "ok" else ai["status"],
        "analytics": analytics["status"],
        "errors_logged": analytics["errors_logged"],
        "rag": rag["status"],
        "whatsapp": whatsapp["status"],
        "redis": redis["status"],
        "runtime": {
            "status": "protected" if runtime_load.enabled else "unbounded",
            "max_concurrent_requests": runtime_load.limit,
            "in_flight_requests": runtime_load.in_flight,
            "available_request_slots": runtime_load.available_slots,
            "queue_timeout_seconds": runtime_load.queue_timeout_seconds,
        },
        "cloud_run": {
            "memory": settings.cloud_run_memory,
            "concurrency": settings.cloud_run_concurrency,
        },
        "sentry": {
            "status": "configured" if settings.sentry_dsn else "not_configured",
            "configured": bool(settings.sentry_dsn),
        },
        "database_detail": database,
        "ai_detail": ai,
        "analytics_detail": analytics,
        "rag_detail": rag,
        "whatsapp_detail": whatsapp,
        "redis_detail": redis,
        "disk": disk,
        "memory": memory,
    }


def production_launch_metrics() -> dict[str, Any]:
    # PROD-LAUNCH-1: Extra launch metrics for Cloud Run/domain smoke checks, without exposing secrets.
    try:
        from app.database import SessionLocal
        from app.models import Patient
        from models.medicine import Medicine
        from models.supplier import Supplier

        db = SessionLocal()
        try:
            medicines_count = int(db.query(Medicine).count())
            suppliers_count = int(db.query(Supplier).count())
            patients_active = int(db.query(Patient).count())
        finally:
            db.close()
    except Exception:
        medicines_count = 0
        suppliers_count = 0
        patients_active = 0

    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "sentry": bool(settings.sentry_dsn),
        "cloud_run_detected": bool(__import__("os").getenv("K_SERVICE")),
        "cloud_run_service": __import__("os").getenv("K_SERVICE", ""),
        "medicines_count": medicines_count,
        "suppliers_count": suppliers_count,
        "patients_active": patients_active,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
