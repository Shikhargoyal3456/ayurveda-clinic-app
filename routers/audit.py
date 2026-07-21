from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.portal_auth import get_portal_user
from models.audit_log import AuditLog


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/admin/audit", tags=["audit"])


@router.get("")
def audit_page(request: Request, db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is None or getattr(user.role, "value", str(user.role)) != "admin":
        return RedirectResponse(url="/new/login", status_code=303)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        "admin/audit_logs.html",
        {"request": request, "user": user, "logs": logs},
    )


@router.get("/api")
def audit_api(request: Request, db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is None or getattr(user.role, "value", str(user.role)) != "admin":
        return {"success": False, "logs": []}
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return {
        "success": True,
        "logs": [
            {
                "id": log.id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "user_id": log.user_id,
                "actor_role": log.actor_role,
                "details": log.details or {},
                "ip_address": log.ip_address,
            }
            for log in logs
        ],
    }
