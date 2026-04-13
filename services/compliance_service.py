from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from services.analytics_service import load_events


def _has_event(event_name: str) -> bool:
    try:
        return any(item.get("event_name") == event_name for item in load_events())
    except Exception:
        return False


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except Exception:
        return False


def get_compliance_status() -> dict[str, Any]:
    events_path = settings.logs_dir / "events.jsonl"
    errors_path = settings.logs_dir / "errors.jsonl"
    return {
        "consent_tracking": _has_event("patient_consent_given"),
        "error_logging": _path_exists(errors_path),
        "audit_logging": _path_exists(settings.audit_log_path),
        "data_logging_active": _path_exists(events_path),
    }
