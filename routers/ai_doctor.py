import json
import os
import re
import uuid
from collections import defaultdict
from time import time

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.ai_provider import generate_gemini_content, is_gemini_configured
from shared.template_engine import render_template, templates


load_dotenv()

router = APIRouter(tags=["ai-doctor"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
MAX_HISTORY_MESSAGES = 100
MAX_MESSAGE_CHARS = 2000
INDIA_EMERGENCY_NUMBERS = """
INDIA EMERGENCY CONTACTS:
- All emergencies (medical/police/fire): 112
- Ambulance only: 102 or 108
- Mental health / suicide prevention: iCall 9152987821 (Mon-Sat 10am-8pm)
- Mental health 24x7: Vandrevala Foundation 1860-2662-345
- Poison Control: 1800-116-1117
"""

AGE_SAFETY_RULES = """
CRITICAL AGE AND DOSAGE SAFETY RULES:
- NEVER recommend specific dosages unless BOTH patient_age AND patient_weight are provided
- If either is missing, say: "I need your age and weight to suggest safe dosages. Please consult a pharmacist or doctor."
- If patient_age < 2: Say "Do not give any over-the-counter medication to infants without a pediatrician's approval."
- If patient_age < 12: Say "Consult a pediatrician. Never use adult medication dosages for children."
- If patient_age > 65: Say "Start with the lowest possible dose. Elderly patients have higher risk of drug interactions — consult a doctor."
"""

SAFETY_DISCLAIMER = "\n\n⚠️ I am an AI assistant, not a licensed doctor. This is health information, not medical advice. Always consult a qualified doctor before making medical decisions. For emergencies in India, call 112."

SYSTEM_PROMPT = f"""You are Dr. Kash, an experienced medical doctor (MBBS) practicing evidence-based modern medicine.

ABSOLUTE RULES:
1. GENERATE ALL RESPONSES DYNAMICALLY - Never repeat the same response twice
2. BASE ADVICE ON CURRENT MEDICAL GUIDELINES (as of 2025)
3. BE SPECIFIC - Give actual medicine names, dosages, and instructions when medically appropriate
4. ASK MAX 2 QUESTIONS per response
5. DETECT EMERGENCIES in first 5 words
6. MATCH THE PATIENT'S LANGUAGE (English or Hindi/Hinglish)
7. DO NOT use canned templates, boilerplate diagnoses, or fixed medicine lists
8. If patient context is incomplete or a medicine/dosage is unsafe to infer, say what extra detail is needed instead of inventing it

EMERGENCY DETECTION (Respond immediately):
- Chest pain + arm/jaw -> "⚠️ EMERGENCY: Possible heart attack. Call 112 NOW."
- Difficulty breathing -> "⚠️ EMERGENCY: Call 112. Sit upright."
- Suicidal thoughts -> "⚠️ CRISIS: Call iCall: 9152987821 or Vandrevala: 1860-2662-345 now."
- Severe bleeding -> "⚠️ EMERGENCY: Apply pressure. Call 112."
- Stroke signs (face droop, arm weakness, speech slur) -> "⚠️ EMERGENCY: Call 112. Note time symptoms started."
- High fever 104°F+ in child -> "⚠️ URGENT: Go to ER."

{INDIA_EMERGENCY_NUMBERS.strip()}

{AGE_SAFETY_RULES.strip()}
"""

DIAGNOSIS_SUFFIX = """

STRUCTURED OUTPUT RULE:
When you have enough information, append this exact machine-readable block at the very end:
|||DIAGNOSIS|||{"items":[{"name":"Condition","seek_doctor":true,"color":"#3b82f6"}]}|||END|||
Only include JSON inside the block. Keep 2-3 items max. If you are not ready, skip the block.
"""

DIAGNOSIS_PATTERN = re.compile(r"\|\|\|DIAGNOSIS\|\|\|(.*?)\|\|\|END\|\|\|", re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""

class ChatRequest(BaseModel):
    message: str
    messages: list[ChatMessage] = Field(default_factory=list)
    language: str = "en"
    patient_age: int | None = None
    patient_weight: float | None = None
    allergies: str | None = None
    current_medications: str | None = None

class ChatResponse(BaseModel):
    reply: str
    diagnosis: dict

def _sanitize_text(value: str) -> str:
    text = HTML_TAG_PATTERN.sub("", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_MESSAGE_CHARS]

def _extract_reply_and_diagnosis(text: str) -> tuple[str, dict]:
    diagnosis = {"items": []}
    clean_reply = (text or "").strip()
    match = DIAGNOSIS_PATTERN.search(clean_reply)
    if match:
        raw_json = match.group(1).strip()
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                diagnosis = parsed
        except json.JSONDecodeError:
            diagnosis = {"items": []}
        clean_reply = DIAGNOSIS_PATTERN.sub("", clean_reply).strip()
    clean_reply = re.sub(r"\n{3,}", "\n\n", clean_reply)
    return clean_reply, diagnosis

def _append_safety_disclaimer(text: str) -> str:
    clean = str(text or "").strip()
    return f"{clean}{SAFETY_DISCLAIMER}" if clean else SAFETY_DISCLAIMER.strip()

def _chunk_text(text: str, size: int = 180) -> list[str]:
    clean = str(text or "")
    return [clean[index:index + size] for index in range(0, len(clean), size)] or [""]

def _generate_gemini_content(prompt: str) -> str:
    try:
        return generate_gemini_content(
            prompt,
            model_name=GEMINI_MODEL,
            model_candidates=[DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

@router.post("/api/doctor/chat", response_model=ChatResponse)
async def doctor_chat(payload: ChatRequest, request: Request):
    if not is_gemini_configured():
        raise HTTPException(status_code=500, detail="Vertex AI Gemini is not configured. Set VERTEX_AI_PROJECT and authenticate with ADC.")
    
    prompt = f"{SYSTEM_PROMPT}\n\nPatient: {payload.message}\n\nDr. Kash:"
    raw_text = _generate_gemini_content(prompt)
    reply, diagnosis = _extract_reply_and_diagnosis(raw_text)
    reply = _append_safety_disclaimer(reply)
    return {"reply": reply, "diagnosis": diagnosis}

@router.post("/api/doctor/chat/stream")
async def doctor_chat_stream(payload: ChatRequest, request: Request):
    if not is_gemini_configured():
        raise HTTPException(status_code=500, detail="Vertex AI Gemini is not configured. Set VERTEX_AI_PROJECT and authenticate with ADC.")
    
    prompt = f"{SYSTEM_PROMPT}\n\nPatient: {payload.message}\n\nDr. Kash:"
    raw_text = _generate_gemini_content(prompt)
    reply, diagnosis = _extract_reply_and_diagnosis(raw_text)
    reply = _append_safety_disclaimer(reply)
    
    async def generate():
        for chunk_text in _chunk_text(reply):
            yield f"data: {json.dumps({'chunk': chunk_text})}\n\n"
        if diagnosis.get("items"):
            diagnosis_json = json.dumps(diagnosis, separators=(",", ":"))
            yield f"data: {json.dumps({'chunk': f'|||DIAGNOSIS|||{diagnosis_json}|||END|||'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/ai-doctor-live")
async def ai_doctor_live_page(request: Request):
    return render_template(templates, request, "doctor.html")
