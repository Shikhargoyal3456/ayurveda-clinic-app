from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.health import build_health_report, database_health, production_launch_metrics
from app.monitoring import metrics
from services.ai_provider import is_gemini_configured
try:
    from services.cache_service import redis_ping
except Exception:
    async def redis_ping() -> bool | None:
        return None


router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Detailed health check")
async def healthz():
    report, launch_metrics, redis_ok = await asyncio.gather(
        run_in_threadpool(build_health_report),
        run_in_threadpool(production_launch_metrics),
        redis_ping(),
    )
    report.update(launch_metrics)
    report["redis_ping"] = redis_ok if redis_ok is not None else "not_configured"
    report["launch_status"] = "healthy" if report.get("status") == "ok" else report.get("status", "degraded")
    return JSONResponse(report)


@router.get("/health", summary="Simple production health check")
async def health_check():
    db_status = "disconnected"
    overall_status = "ok"
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        overall_status = "degraded"
    finally:
        db.close()

    return {
        "status": overall_status,
        "db": db_status,
        "ai": "configured" if is_gemini_configured() else "not configured",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version,
    }


@router.get("/health/deep", summary="Deep dependency health check")
async def deep_health_check():
    checks = build_health_report()
    monitoring = metrics.get_metrics()
    backup_dir = settings.backups_dir
    latest_backup = None
    backup_status = "not_configured" if not settings.backup_enabled else "missing"
    if backup_dir.exists():
        backups = sorted(backup_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if backups:
            latest = backups[0]
            latest_backup = {
                "name": latest.name,
                "modified_at": datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": latest.stat().st_size,
            }
            backup_status = "healthy"

    status_value = "healthy"
    if checks.get("status") not in {"ok", "healthy"}:
        status_value = "degraded"
    if checks.get("database") == "error":
        status_value = "unhealthy"

    return {
        "status": status_value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": checks.get("database_detail", {}),
            "redis": checks.get("redis_detail", {}),
            "disk_space": checks.get("disk", {}),
            "memory": checks.get("memory", {}),
            "runtime": checks.get("runtime", {}),
            "backup": {"status": backup_status, "latest": latest_backup},
        },
        "monitoring": monitoring,
    }
