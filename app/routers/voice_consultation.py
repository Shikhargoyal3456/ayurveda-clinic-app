from __future__ import annotations

import re

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
    structured = await structure_case_sheet(transcript, patient_name=patient_name)
    symptoms = structured.get("symptoms") or []
    patient_age = structured.get("age")
    patient_gender = structured.get("gender") or ""
    if not any(re.search(pattern, transcript, re.IGNORECASE) for pattern in (r"\b\d{1,3}\s*(?:years?\s*old|year-old|yrs?\b)", r"\bage\s*(?:is\s*)?\d{1,3}\b")):
        patient_age = None
    if not re.search(r"\b(male|female|man|woman|boy|girl|he|she|his|her)\b", transcript, re.IGNORECASE):
        patient_gender = ""
    extracted = {
        "patient_name": structured.get("patient_name") or patient_name,
        "age": patient_age,
        "gender": patient_gender,
        "symptoms": symptoms,
        "duration": structured.get("duration") or structured.get("duration_of_illness") or "",
    }

    return {
        "success": True,
        "extracted": extracted,
        "patient": {
            "name": structured.get("patient_name") or patient_name,
            "age": patient_age,
            "gender": patient_gender,
            "phone": "",
        },
        "symptoms": symptoms,
        "diagnosis": structured.get("diagnosis") or "",
        "medicines": structured.get("medicines") or [],
        "follow_up": structured.get("follow_up") or "",
        "transcript": transcript,
        "structured_data": structured,
    }

