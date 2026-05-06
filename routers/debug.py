from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.portal_auth import get_portal_user
from models.user import User, UserRole
from shared.template_engine import templates


router = APIRouter(tags=["debug"])


@router.get("/debug/session", response_class=HTMLResponse)
def debug_session(request: Request, db: Session = Depends(get_db)):
    session_info = dict(request.session)
    user_id = session_info.get("portal_user_id")
    user_info = None
    if user_id:
        user = db.get(User, int(user_id))
        if user is not None:
            user_info = {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
                "is_active": bool(user.is_active),
                "is_verified": bool(user.is_verified),
            }

    active_user = get_portal_user(request, db)
    active_user_info = None
    if active_user is not None:
        active_user_info = {
            "id": active_user.id,
            "email": active_user.email,
            "full_name": active_user.full_name,
            "role": active_user.role.value if isinstance(active_user.role, UserRole) else str(active_user.role),
        }

    return templates.TemplateResponse(
        request,
        "debug_session.html",
        {
            "request": request,
            "session_info": session_info,
            "user_info": user_info,
            "active_user_info": active_user_info,
        },
    )
