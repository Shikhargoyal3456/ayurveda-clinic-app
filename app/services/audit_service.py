from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import settings
from models.audit_log import AuditLog


class AuditService:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def log_action(
        self,
        request: Request | None,
        action: str,
        resource: str | None = None,
        resource_id: str | int | None = None,
        details: dict[str, Any] | None = None,
        user_id: int | None = None,
        actor_role: str | None = None,
    ) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "resource": resource,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "details": details or {},
            "user_id": user_id,
            "actor_role": actor_role,
            "ip_address": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent") if request else None,
        }
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        audit_path = settings.audit_log_path
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        if self.db is not None:
            self.db.add(
                AuditLog(
                    user_id=user_id,
                    actor_role=actor_role,
                    action=action,
                    resource=resource,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    details=details,
                    ip_address=payload["ip_address"],
                    user_agent=payload["user_agent"],
                )
            )
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
