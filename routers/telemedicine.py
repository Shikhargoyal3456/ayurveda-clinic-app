from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Appointment, Doctor, Patient
from app.portal_auth import dashboard_path_for_role, get_portal_user, normalize_identifier
from services.ai_order_automation import AIOrderAutomation
from services.ai_support_automation import AISupportAutomation
from services.feature_flags import is_ai_automation_enabled, is_telemedicine_enabled
from services.telemedicine_service import TelemedicineService


router = APIRouter(tags=["telemedicine"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
telemedicine_service = TelemedicineService()
ai_order = AIOrderAutomation()
ai_support = AISupportAutomation()
logger = logging.getLogger(__name__)


class TelemedicineSessionCreate(BaseModel):
    patient_id: int
    doctor_id: int
    session_type: str = "video"


class SymptomAnalysisRequest(BaseModel):
    symptoms: str = Field(default="")


class TelemedicineAssistRequest(BaseModel):
    session_id: str
    conversation: list[str] | str


class TelemedicineSummaryRequest(BaseModel):
    session_id: str


class SupportQueryRequest(BaseModel):
    query: str
    user_context: dict[str, Any] = Field(default_factory=dict)


class FraudCheckRequest(BaseModel):
    order_data: dict[str, Any]


class TicketRouteRequest(BaseModel):
    id: int | None = None
    user_id: int = 0
    message: str = ""


class AlternativesRequest(BaseModel):
    medicine_name: str


@router.get("/telemedicine/symptom-checker")
def symptom_checker_page(request: Request):
    _ensure_telemedicine_enabled()
    return templates.TemplateResponse(
        request,
        "telemedicine/symptom_checker.html",
        {
            "request": request,
            "active_page": "consult",
            "user_role": "AI triage",
            "avatar_label": "AI",
        },
    )


@router.get("/telemedicine/book")
def telemedicine_booking_page(request: Request, db: Session = Depends(get_db)):
    _ensure_telemedicine_enabled()
    portal_user = get_portal_user(request, db)
    if portal_user is None and getattr(request.state, "user", None) is None:
        doctors = telemedicine_service._recommend_doctors()
        return templates.TemplateResponse(
            request,
            "telemedicine/guest_book.html",
            {
                "request": request,
                "doctors": doctors,
                "requires_login": True,
                "active_page": "consult",
                "user_role": "Guest access",
                "avatar_label": "TM",
                "is_guest_user": True,
            },
        )

    role = _current_session_role(request, portal_user)
    if role == "patient":
        doctors = telemedicine_service._recommend_doctors()
        return templates.TemplateResponse(
            request,
            "telemedicine/patient_book.html",
            {
                "request": request,
                "doctors": doctors,
                "active_page": "consult",
                "user_role": "Video consultation",
                "avatar_label": "TM",
            },
        )

    if role == "doctor":
        legacy_doctor = _resolve_legacy_doctor(request, db, portal_user)
        if legacy_doctor is None:
            raise HTTPException(status_code=404, detail="Doctor profile not found")
        dashboard = _doctor_consultation_dashboard(db, legacy_doctor.id)
        return templates.TemplateResponse(
            request,
            "telemedicine/doctor_consultations.html",
            {
                "request": request,
                "active_page": "consult",
                "user_role": "Doctor consultations",
                "avatar_label": "TM",
                **dashboard,
            },
        )

    if portal_user is not None:
        role_slug = getattr(portal_user.role, "value", str(portal_user.role))
        return RedirectResponse(url=dashboard_path_for_role(role_slug), status_code=303)

    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/telemedicine/room/{session_id}")
def telemedicine_room_page(request: Request, session_id: str):
    _ensure_telemedicine_enabled()
    session = telemedicine_service.active_sessions.get(session_id) or telemedicine_service._load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    doctor_name = _doctor_display_name(int(session.get("doctor_id", 0) or 0))
    return templates.TemplateResponse(
        request,
        "telemedicine/video_consult.html",
        {
            "request": request,
            "session_id": session_id,
            "doctor_name": doctor_name,
            "start_time": session.get("start_time", ""),
            "active_page": "consult",
            "user_role": "Video consult",
            "avatar_label": "VC",
            "hide_footer": True,
        },
    )


@router.get("/telemedicine/summary/{session_id}")
async def telemedicine_summary_page(request: Request, session_id: str):
    _ensure_telemedicine_enabled()
    summary = await telemedicine_service.ai_post_consultation_summary(session_id)
    followup = await telemedicine_service.auto_schedule_followup(session_id)
    return templates.TemplateResponse(
        request,
        "telemedicine/summary.html",
        {
            "request": request,
            "summary": summary,
            "followup": followup,
            "active_page": "consult",
            "user_role": "Consult summary",
            "avatar_label": "CS",
        },
    )


@router.get("/ai/order-automation")
async def ai_order_automation_page(request: Request):
    _ensure_ai_enabled()
    sample = await ai_order.auto_categorize_order(
        {
            "id": 101,
            "items": [{"name": "Ashwagandha Tablets", "prescription_required": True}],
        }
    )
    return templates.TemplateResponse(
        request,
        "ai/order_automation.html",
        {
            "request": request,
            "sample": sample,
            "active_page": "profile",
            "user_role": "AI operations",
            "avatar_label": "AO",
        },
    )


@router.get("/ai/support")
def ai_support_page(request: Request):
    _ensure_ai_enabled()
    return templates.TemplateResponse(
        request,
        "support/ai_assistant.html",
        {
            "request": request,
            "active_page": "consult",
            "user_role": "AI support",
            "avatar_label": "AS",
        },
    )


@router.post("/api/telemedicine/create-session")
async def create_telemedicine_session(
    payload: TelemedicineSessionCreate | None = Body(default=None),
    patient_id: int | None = Query(default=None),
    doctor_id: int | None = Query(default=None),
    session_type: str = Query(default="video"),
):
    _ensure_telemedicine_enabled()
    body = payload or TelemedicineSessionCreate(
        patient_id=int(patient_id or 0),
        doctor_id=int(doctor_id or 0),
        session_type=session_type,
    )
    session = await telemedicine_service.create_consultation_session(body.patient_id, body.doctor_id, body.session_type)
    return JSONResponse(session)


@router.post("/api/telemedicine/analyze-symptoms")
async def analyze_symptoms(payload: SymptomAnalysisRequest):
    _ensure_telemedicine_enabled()
    try:
        result = await telemedicine_service.analyze_symptoms(payload.symptoms)
    except Exception as exc:
        logger.exception("Telemedicine symptom analysis failed: %s", exc)
        return JSONResponse({"success": False, "error": str(exc), "source": "ai_error"}, status_code=503)
    return JSONResponse(result)


@router.post("/api/telemedicine/ai-assist")
async def ai_assist_during_consultation(payload: TelemedicineAssistRequest):
    _ensure_telemedicine_enabled()
    insights = await telemedicine_service.real_time_ai_assistant(payload.session_id, payload.conversation)
    return JSONResponse(insights)


@router.post("/api/telemedicine/summary")
async def get_consultation_summary(payload: TelemedicineSummaryRequest):
    _ensure_telemedicine_enabled()
    summary = await telemedicine_service.ai_post_consultation_summary(payload.session_id)
    return JSONResponse(summary)


@router.post("/api/telemedicine/summary/{session_id}")
async def get_consultation_summary_by_id(session_id: str):
    _ensure_telemedicine_enabled()
    summary = await telemedicine_service.ai_post_consultation_summary(session_id)
    return JSONResponse(summary)


@router.websocket("/ws/telemedicine/{session_id}")
async def telemedicine_websocket(websocket: WebSocket, session_id: str):
    if not is_telemedicine_enabled():
        await websocket.close(code=1013)
        return
    await websocket.accept()
    await telemedicine_service.register_socket(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await telemedicine_service.handle_signaling(session_id, data, sender=websocket)
    except WebSocketDisconnect:
        await telemedicine_service.handle_disconnect(session_id, websocket)


@router.post("/api/ai/order/process/{order_id}")
async def ai_process_order(order_id: int):
    _ensure_ai_enabled()
    result = await ai_order.process_order_with_ai(order_id)
    return JSONResponse(result)


@router.post("/api/ai/order/fraud-check")
async def ai_fraud_check(payload: FraudCheckRequest | dict[str, Any] = Body(...)):
    _ensure_ai_enabled()
    order_data = payload.order_data if isinstance(payload, FraudCheckRequest) else payload
    result = await ai_order.auto_detect_fraud(order_data)
    return JSONResponse(result)


@router.post("/api/ai/support/respond")
async def ai_support_response(payload: SupportQueryRequest | None = Body(default=None), query: str | None = Query(default=None)):
    _ensure_ai_enabled()
    request_payload = payload or SupportQueryRequest(query=str(query or ""), user_context={})
    result = await ai_support.auto_respond_to_query(request_payload.query, request_payload.user_context)
    return JSONResponse(result)


@router.post("/api/ai/support/route-ticket")
async def ai_route_support_ticket(payload: TicketRouteRequest):
    _ensure_ai_enabled()
    result = await ai_support.auto_ticket_routing(payload.model_dump())
    return JSONResponse(result)


@router.post("/api/ai/medicine/alternatives")
async def get_medicine_alternatives(payload: AlternativesRequest | None = Body(default=None), medicine_name: str | None = Query(default=None)):
    _ensure_ai_enabled()
    request_payload = payload or AlternativesRequest(medicine_name=str(medicine_name or ""))
    alternatives = await ai_order.auto_suggest_alternatives(request_payload.medicine_name)
    return JSONResponse({"alternatives": alternatives})


@router.post("/api/ai/refill/remind/{user_id}")
async def refill_reminder(user_id: int):
    _ensure_ai_enabled()
    reminder = await ai_order.auto_refill_reminder(user_id)
    return JSONResponse(reminder)


@router.get("/api/ai/delivery/optimize")
async def optimize_delivery_routes():
    _ensure_ai_enabled()
    orders: list[dict[str, Any]] = []
    optimized = await ai_order.auto_optimize_delivery_route(orders)
    return JSONResponse(optimized)


def _ensure_telemedicine_enabled() -> None:
    if not is_telemedicine_enabled():
        raise HTTPException(status_code=503, detail="Telemedicine module is disabled.")


def _ensure_ai_enabled() -> None:
    if not is_ai_automation_enabled():
        raise HTTPException(status_code=503, detail="AI automation module is disabled.")


def _doctor_display_name(doctor_id: int) -> str:
    if doctor_id <= 0:
        return "Kash AI Doctor"
    db = SessionLocal()
    try:
        doctor = db.get(Doctor, doctor_id)
        if doctor is None:
            return "Kash AI Doctor"
        return doctor.full_name or doctor.username
    except Exception as exc:
        logger.warning("Doctor lookup failed for telemedicine room %s: %s", doctor_id, exc)
        return "Kash AI Doctor"
    finally:
        db.close()


def _current_session_role(request: Request, portal_user: Any | None) -> str:
    if portal_user is not None:
        return getattr(portal_user.role, "value", str(portal_user.role))
    if getattr(request.state, "user", None) is not None:
        return "doctor"
    return ""


def _resolve_legacy_doctor(request: Request, db: Session, portal_user: Any | None) -> Doctor | None:
    legacy_doctor = getattr(request.state, "user", None)
    if legacy_doctor is not None:
        return legacy_doctor
    if portal_user is None:
        return None
    username = normalize_identifier(getattr(portal_user, "email", "") or getattr(portal_user, "phone", "") or f"doctor-{portal_user.id}")
    return db.query(Doctor).filter(Doctor.username == username).first()


def _doctor_consultation_dashboard(db: Session, doctor_id: int) -> dict[str, Any]:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    appointments = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .options(joinedload(Appointment.patient))
        .filter(Patient.doctor_id == doctor_id, Appointment.date >= today)
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .limit(50)
        .all()
    )
    weekly_appointments = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(
            Patient.doctor_id == doctor_id,
            Appointment.date >= week_start,
            Appointment.date <= week_end,
        )
        .all()
    )
    completed_this_week = sum(1 for item in weekly_appointments if str(item.status or "").strip().lower() in {"completed", "done"})
    upcoming_appointments: list[dict[str, Any]] = []
    todays_consultations = 0
    for item in appointments:
        patient = item.patient
        if patient is None:
            continue
        if item.date == today:
            todays_consultations += 1
        upcoming_appointments.append(
            {
                "id": item.id,
                "patient_id": patient.id,
                "patient_name": patient.name,
                "patient_age": patient.age,
                "date": item.date.strftime("%d %b %Y") if item.date else "",
                "time": _format_appointment_time(item.time),
                "reason": item.reason or "General consultation",
                "status": (item.status or "scheduled").lower(),
            }
        )
    return {
        "doctor_id": doctor_id,
        "upcoming_count": todays_consultations,
        "total_upcoming": len(upcoming_appointments),
        "completed_this_week": completed_this_week,
        "upcoming_appointments": upcoming_appointments,
    }


def _format_appointment_time(value: str) -> str:
    raw = str(value or "").strip()
    for pattern in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            parsed = datetime.strptime(raw, pattern)
            return parsed.strftime("%I:%M %p")
        except ValueError:
            continue
    return raw or "Scheduled"
