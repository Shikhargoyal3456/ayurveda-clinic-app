from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.ai_fallback import fallback_health_status
from app.config import settings
from app.database import engine
from app.rag_engine import get_rag_engine
from services.ai_provider import GROQ_API_KEY
from services.whatsapp import whatsapp_health_status


def database_health() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def ai_health() -> dict[str, Any]:
    engine_instance = get_rag_engine()
    available, message = engine_instance.ensure_ollama_available(timeout_seconds=2, allow_retries=False)
    fallback = fallback_health_status()
    gemini_configured = bool(settings.gemini_api_key)
    groq_configured = bool(GROQ_API_KEY)
    primary_provider = "gemini" if gemini_configured else "ollama"
    ai_available = available or gemini_configured
    status_message = message
    if gemini_configured and not available:
        status_message = "Gemini is configured and available as the primary AI provider."
    return {
        "status": "ok" if ai_available else "degraded",
        "available": ai_available,
        "fallback_mode": not ai_available,
        "message": status_message,
        "primary_provider": primary_provider,
        "gemini_configured": gemini_configured,
        "groq_configured": groq_configured,
        "ollama_reachable": available,
        "fallback": fallback,
    }


def rag_health() -> dict[str, Any]:
    engine_instance = get_rag_engine()
    docs_path = engine_instance._docs_path()
    faiss_path = engine_instance._faiss_path()
    return {
        "status": "ok" if docs_path.exists() and faiss_path.exists() else "degraded",
        "docs_indexed": docs_path.exists(),
        "faiss_index_ready": faiss_path.exists(),
        "vector_store_dir": str(settings.vector_store_dir),
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


def build_health_report() -> dict[str, Any]:
    database = database_health()
    ai = ai_health()
    rag = rag_health()
    whatsapp = whatsapp_health_status()
    disk = disk_health()
    memory = memory_health()
    overall = "ok"
    if any(item.get("status") == "error" for item in (database, ai, rag, disk)):
        overall = "degraded"
    return {
        "status": overall,
        "api": "ok",
        "version": settings.app_version,
        "database": database["status"],
        "ai": ai["status"],
        "rag": rag["status"],
        "whatsapp": whatsapp["status"],
        "database_detail": database,
        "ai_detail": ai,
        "rag_detail": rag,
        "whatsapp_detail": whatsapp,
        "disk": disk,
        "memory": memory,
    }
