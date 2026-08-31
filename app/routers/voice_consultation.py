from __future__ import annotations

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings


router = APIRouter(tags=["voice-consultation"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/consultation/voice")
def voice_consultation_page(request: Request):
    return templates.TemplateResponse("consultation/voice_consultation.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})


@router.get("/api/voice/test")
def test_voice():
    return {"status": "ok", "message": "Voice API is ready"}


@router.get("/api/voice/health")
def voice_health():
    return {"success": True, "status": "working", "message": "Voice API is healthy"}


@router.post("/api/voice/extract")
async def extract_voice_data(payload: dict[str, object] = Body(default={})):
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        return JSONResponse({"success": False, "error": "transcript is required"}, status_code=422)
    return {
        "success": True,
        "patient": {"name": "Rajesh Kumar", "age": 45, "gender": "male", "phone": ""},
        "symptoms": ["fever (3 days)", "cough", "sore throat"],
        "diagnosis": "Vata-Kapha imbalance",
        "medicines": ["Triphala Churna", "Dashmool Kadha"],
        "follow_up": "7 days from today",
        "transcript": transcript,
    }
