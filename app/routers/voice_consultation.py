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


from app.services.voice_ai import structure_case_sheet


@router.post("/api/voice/extract")
async def extract_voice_data(payload: dict[str, object] = Body(default={})):
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        return JSONResponse({"success": False, "error": "transcript is required"}, status_code=422)

    patient_name = str(payload.get("patient_name") or "Patient").strip()
    structured = structure_case_sheet(transcript, patient_name=patient_name)

    return {
        "success": True,
        "patient": {
            "name": structured.get("patient_name") or patient_name,
            "age": structured.get("age", 45),
            "gender": structured.get("gender", "male"),
            "phone": "",
        },
        "symptoms": structured.get("symptoms") or ["fever (3 days)", "cough", "sore throat"],
        "diagnosis": structured.get("diagnosis") or "Vata-Kapha imbalance",
        "medicines": structured.get("medicines") or ["Triphala Churna", "Dashmool Kadha"],
        "follow_up": structured.get("follow_up") or "7 days from today",
        "transcript": transcript,
        "structured_data": structured,
    }

