from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Request

from app.config import settings

_audit_lock = Lock()


def _audit_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.audit_log_path


def write_audit_event(event: str, request: Request | None = None, **details: Any) -> None:
    actor_id = None
    client_ip = None
    user_agent = None

    if request is not None:
        actor_id = request.session.get("doctor_id")
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor_id": actor_id,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "details": details,
    }

    with _audit_lock:
        with _audit_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
