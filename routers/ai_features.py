from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.ai_business_intelligence import AIBusinessIntelligence
from services.ai_chatbot import AIHealthcareChatbot
from services.ai_image_analyzer import AIImageAnalyzer
from services.ai_personalization import AIPersonalizationEngine
from services.ai_prescription_scanner import AIPrescriptionScanner
from services.ai_voice_assistant import AIVoiceAssistant


router = APIRouter(tags=["ai-features"])
prescription_scanner = AIPrescriptionScanner()
voice_assistant = AIVoiceAssistant()
image_analyzer = AIImageAnalyzer()
chatbot = AIHealthcareChatbot()
personalization = AIPersonalizationEngine()
bi = AIBusinessIntelligence()


class ChatRequest(BaseModel):
    message: str = Field(default="")


@router.post("/api/ai/scan-prescription")
async def scan_prescription(file: UploadFile = File(...), user_id: int = Form(default=0)):
    result = await prescription_scanner.scan_prescription(file.file, user_id=user_id, image_name=file.filename or "")
    return JSONResponse(result)


@router.post("/api/ai/voice-command")
async def voice_command(file: UploadFile = File(...)):
    result = await voice_assistant.process_voice_command(file.file)
    return JSONResponse(result)


@router.post("/api/ai/analyze-symptom-image")
async def analyze_symptom_image(file: UploadFile = File(...), symptom_type: str = Form(...)):
    result = await image_analyzer.analyze_symptom_image(file.file, symptom_type)
    return JSONResponse(result)


@router.post("/api/ai/chat/{user_id}")
async def chat(user_id: int, payload: ChatRequest | dict[str, Any] = Body(...)):
    if isinstance(payload, ChatRequest):
        message = payload.message
    else:
        message = str(payload.get("message", ""))
    result = await chatbot.chat(user_id, message)
    return JSONResponse(result)


@router.get("/api/ai/feed/{user_id}")
async def personalized_feed(user_id: int):
    return JSONResponse(await personalization.get_personalized_feed(user_id))


@router.get("/api/ai/predict-next/{user_id}")
async def predict_next_purchase(user_id: int):
    return JSONResponse(await personalization.predict_next_purchase(user_id))


@router.get("/api/ai/health-insights/{user_id}")
async def health_insights(user_id: int):
    return JSONResponse(await personalization.get_health_insights(user_id))


@router.get("/api/ai/forecast-demand/{product_id}")
async def forecast_demand(product_id: int, days: int = 30):
    return JSONResponse(await bi.forecast_demand(product_id, days))


@router.get("/api/ai/forecast-revenue")
async def forecast_revenue(days: int = 90):
    return JSONResponse(await bi.revenue_forecast(days))


@router.get("/api/ai/churn-prediction")
async def predict_churn():
    return JSONResponse(await bi.customer_churn_prediction())
