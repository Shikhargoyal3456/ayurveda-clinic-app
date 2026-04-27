from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.health import build_health_report, database_health, production_launch_metrics
try:
    from services.cache_service import redis_ping
except Exception:
    async def redis_ping() -> bool:
        return False


router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Detailed health check")
async def healthz():
    report = build_health_report()
    report.update(production_launch_metrics())
    report["redis_ping"] = await redis_ping()
    report["launch_status"] = "healthy" if report.get("status") == "ok" else report.get("status", "degraded")
    return JSONResponse(report)


@router.get("/health", summary="Simple production health check")
async def health_check():
    db = database_health()
    return {
        "status": "healthy" if db.get("status") == "ok" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if db.get("status") == "ok" else "disconnected",
        "version": settings.app_version,
    }
