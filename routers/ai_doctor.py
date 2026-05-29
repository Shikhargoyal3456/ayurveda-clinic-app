from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.portal_auth import require_portal_roles
from models.user import User
from services.ai_live_doctor import AILiveDoctorService
from shared.template_engine import render_template, templates


router = APIRouter(tags=["ai-doctor"])
logger = logging.getLogger(__name__)
ai_live_doctor = AILiveDoctorService()


@router.get("/ai-doctor")
def ai_doctor_page(request: Request, user: User = Depends(require_portal_roles("patient"))):
    return render_template(
        templates,
        request,
        "ai_doctor.html",
        {
            "active_page": "consult",
            "user_name": user.full_name or "Patient",
            "user_role": "AI Doctor Consultation",
            "avatar_label": "DR",
            "page_hint": "Live, multimodal AI guidance with calm support",
            "book_appointment_url": "/telemedicine/book",
        },
    )


@router.websocket("/ws/ai-doctor")
async def ai_doctor_websocket(websocket: WebSocket):
    user = await _authenticate_patient_socket(websocket)
    if user is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    session, initial_events = ai_live_doctor.start_session(user)
    try:
        for event in initial_events:
            await websocket.send_json(event)

        while True:
            payload = await websocket.receive_json()
            events = await ai_live_doctor.handle_event(session.session_id, payload)
            for event in events:
                await websocket.send_json(event)
    except WebSocketDisconnect:
        ai_live_doctor.close_session(session.session_id)
    except Exception as exc:
        logger.exception("AI doctor websocket failed: %s", exc)
        await websocket.send_json({"type": "error", "message": "AI doctor connection dropped. Please try again."})
        ai_live_doctor.close_session(session.session_id)


async def _authenticate_patient_socket(websocket: WebSocket) -> User | None:
    session_data = websocket.scope.get("session") or {}
    user_id = session_data.get("portal_user_id")
    role = str(session_data.get("portal_user_role") or session_data.get("portal_role") or "")
    if not user_id or role != "patient":
        return None

    db: Session = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        if user is None or not user.is_active:
            return None
        user_role = getattr(user.role, "value", str(user.role))
        if user_role != "patient":
            return None
        return user
    except Exception as exc:
        logger.warning("AI doctor websocket auth failed: %s", exc)
        return None
    finally:
        db.close()
