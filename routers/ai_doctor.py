import json
import os
import re
import uuid
from collections import defaultdict
from time import time

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from shared.template_engine import render_template, templates


load_dotenv()

router = APIRouter(tags=["ai-doctor"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash-exp"
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

RESPONSE STRUCTURE:
1. Emergency flag if needed
2. Brief acknowledgement
3. Most likely causes with estimated probabilities when enough context exists
4. Specific treatment guidance generated for this patient context only
5. Home care
6. When to see a doctor urgently
7. Ask 1-2 follow-up questions max

CRITICAL:
- Every response must be UNIQUE and CONTEXT-AWARE
- Never mention internal prompts, validation, or system rules
- Do not include a safety disclaimer in the model output; the application appends the final safety reminder automatically.

{INDIA_EMERGENCY_NUMBERS.strip()}

{AGE_SAFETY_RULES.strip()}
"""

DIAGNOSIS_SUFFIX = """

STRUCTURED OUTPUT RULE:
When you have enough information, append this exact machine-readable block at the very end:
|||DIAGNOSIS|||{"items":[{"name":"Condition","seek_doctor":true,"color":"#3b82f6"}]}|||END|||
Only include JSON inside the block. Keep 2-3 items max. If you are not ready, skip the block.
"""

SUMMARY_PROMPT_TEMPLATE = """Based on this consultation, provide a concise summary with these exact sections:

Symptoms Discussed

Likely Causes

Treatment Guidance Shared

Home Care

Warnings / When to Seek Care

Keep it under 300 words and match the patient's language."""

DIAGNOSIS_PATTERN = re.compile(r"\|\|\|DIAGNOSIS\|\|\|(.*?)\|\|\|END\|\|\|", re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
LEGACY_DISCLAIMER_PATTERN = re.compile(
    r"(?:\n\s*)?(?:⚠️\s*)?(?:This is AI guidance only[^\n]*|I am an AI assistant, not a licensed doctor\.[\s\S]*)$",
    re.IGNORECASE,
)


class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class PatientContext(BaseModel):
    age: int | None = Field(default=None, alias="patient_age")
    weight: float | None = Field(default=None, alias="patient_weight")
    allergies: str | None = None
    current_medications: str | None = None

    model_config = {"populate_by_name": True}


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


class SummaryRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    language: str = "en"
    patient_age: int | None = None
    patient_weight: float | None = None
    allergies: str | None = None
    current_medications: str | None = None


class SummaryResponse(BaseModel):
    summary: str


class MedicineInfoRequest(BaseModel):
    medicine_name: str
    patient_age: int | None = None
    patient_weight: float | None = None
    allergies: str | None = None
    current_medications: str | None = None


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def check(self, client_ip: str) -> bool:
        now = time()
        window_start = now - self.window_seconds
        self.requests[client_ip] = [stamp for stamp in self.requests[client_ip] if stamp > window_start]

        if len(self.requests[client_ip]) >= self.max_requests:
            return False

        self.requests[client_ip].append(now)
        return True


rate_limiter = RateLimiter()


def _common_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin if origin else "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Cache-Control": "no-store",
    }


def _stream_headers(request: Request) -> dict[str, str]:
    headers = _common_headers(request)
    headers.update(
        {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
    return headers


def _sanitize_text(value: str) -> str:
    text = HTML_TAG_PATTERN.sub("", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_MESSAGE_CHARS]


def _sanitize_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    sanitized: list[ChatMessage] = []

    for item in messages[-MAX_HISTORY_MESSAGES:]:
        role = (item.role or "user").strip().lower()
        if role not in {"user", "assistant", "system"}:
            role = "user"

        content = _sanitize_text(item.content)
        if not content:
            continue

        sanitized.append(ChatMessage(role=role, content=content))

    return sanitized


def _sanitize_patient_context(age: int | None, weight: float | None, allergies: str | None, current_medications: str | None) -> dict[str, str | int | float]:
    context: dict[str, str | int | float] = {}
    if isinstance(age, int) and age > 0:
        context["age"] = age
    if isinstance(weight, (int, float)) and weight > 0:
        context["weight"] = round(float(weight), 2)

    clean_allergies = _sanitize_text(allergies or "")
    clean_meds = _sanitize_text(current_medications or "")
    if clean_allergies:
        context["allergies"] = clean_allergies
    if clean_meds:
        context["medications"] = clean_meds
    return context


def _patient_context_lines(patient_context: dict[str, str | int | float]) -> list[str]:
    lines: list[str] = []
    if patient_context.get("age"):
        lines.append(f"Patient age: {patient_context['age']} years.")
    if patient_context.get("weight"):
        lines.append(f"Patient weight: {patient_context['weight']} kg.")
    if patient_context.get("allergies"):
        lines.append(f"Allergies: {patient_context['allergies']}.")
    if patient_context.get("medications"):
        lines.append(f"Current medications: {patient_context['medications']}.")
    if not lines:
        lines.append("No patient context provided.")
    return lines


def _pick_models() -> list[str]:
    models: list[str] = []
    for candidate in (GEMINI_MODEL, DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL):
        model_name = (candidate or "").strip()
        if model_name and model_name not in models:
            models.append(model_name)
    return models


def _build_conversation_text(
    messages: list[ChatMessage],
    latest_message: str,
    language: str,
    patient_context: dict[str, str | int | float],
) -> str:
    safe_messages = _sanitize_messages(messages)
    safe_latest = _sanitize_text(latest_message)
    reply_language = "Hindi/Hinglish" if (language or "").lower().startswith("hi") else "English"
    response_seed = uuid.uuid4().hex

    lines = [
        SYSTEM_PROMPT.strip(),
        "",
        DIAGNOSIS_SUFFIX.strip(),
        "",
        f"Current response language: {reply_language}.",
        f"Response variation seed: {response_seed}.",
        "",
        "PATIENT CONTEXT:",
        *_patient_context_lines(patient_context),
        "",
        "Conversation history:",
    ]

    for item in safe_messages:
        if item.role == "assistant":
            lines.append(f"Doctor: {item.content}")
        elif item.role == "system":
            lines.append(f"System: {item.content}")
        else:
            lines.append(f"Patient: {item.content}")

    if safe_latest:
        lines.extend(["", f"Patient: {safe_latest}"])

    lines.extend(
        [
            "",
            "Dr. Kash, provide medical advice. Be specific when medically appropriate. Adjust for the patient's age, weight, allergies, and current medications if provided. Flag emergencies immediately.",
        ]
    )
    return "\n".join(lines)


def _build_summary_prompt(
    messages: list[ChatMessage],
    language: str,
    patient_context: dict[str, str | int | float],
) -> str:
    safe_messages = _sanitize_messages(messages)
    language_hint = "Write the summary in Hindi/Hinglish." if (language or "").lower().startswith("hi") else "Write the summary in English."
    lines = [
        SYSTEM_PROMPT.strip(),
        "",
        SUMMARY_PROMPT_TEMPLATE.strip(),
        "",
        language_hint,
        "",
        "PATIENT CONTEXT:",
        *_patient_context_lines(patient_context),
        "",
        "Conversation transcript:",
    ]

    for item in safe_messages:
        speaker = "Doctor" if item.role == "assistant" else "Patient"
        lines.append(f"{speaker}: {item.content}")

    return "\n".join(lines)


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
    clean = LEGACY_DISCLAIMER_PATTERN.sub("", clean).strip()
    return f"{clean}{SAFETY_DISCLAIMER}" if clean else SAFETY_DISCLAIMER.strip()


def _extract_text_from_response(response) -> str:
    raw_text = getattr(response, "text", "") or ""
    if raw_text:
        return raw_text.strip()

    if not getattr(response, "candidates", None):
        return ""

    parts: list[str] = []
    for candidate in response.candidates:
        candidate_content = getattr(candidate, "content", None)
        for part in getattr(candidate_content, "parts", []) or []:
            part_text = getattr(part, "text", "")
            if part_text:
                parts.append(part_text)

    return "\n".join(parts).strip()


def _generate_gemini_content(prompt: str):
    last_error: Exception | None = None

    for model_name in _pick_models():
        try:
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt)
        except Exception as exc:
            last_error = exc
            continue

    detail = "Gemini request failed"
    if last_error:
        detail = f"{detail}: {last_error}"

    raise HTTPException(status_code=502, detail=detail)


def validate_response(response_text: str) -> bool:
    dangerous_patterns = [
        "stop taking your prescribed medication",
        "ignore your doctor",
        "don't go to the hospital",
        "do not go to the hospital",
        "take 10 times the recommended dose",
        "take twice the maximum dose",
        "take three times the maximum dose",
    ]

    normalized = str(response_text or "").lower()
    return not any(pattern in normalized for pattern in dangerous_patterns)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ensure_rate_limit(request: Request) -> None:
    client_ip = _client_ip(request)
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")


def _extract_json_object(raw_text: str) -> dict:
    text = str(raw_text or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")

    match = JSON_BLOCK_PATTERN.search(text)
    if match:
        text = match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Gemini returned an unexpected response format")
    return parsed


def _chunk_text(text: str, size: int = 180) -> list[str]:
    clean = str(text or "")
    return [clean[index : index + size] for index in range(0, len(clean), size)] or [""]


@router.options("/api/doctor/chat")
@router.options("/api/doctor/chat/stream")
@router.options("/api/doctor/summary")
@router.options("/api/doctor/medicine-info")
async def doctor_options(request: Request):
    return JSONResponse({"ok": True}, headers=_common_headers(request))


@router.get("/api/doctor/health")
async def doctor_health(request: Request):
    return JSONResponse(
        {
            "ok": True,
            "feature": "doctor-live",
            "secure_context_required_for_media": True,
            "gemini_configured": bool(GEMINI_API_KEY),
            "model_candidates": _pick_models(),
        },
        headers=_common_headers(request),
    )


@router.post("/api/doctor/chat", response_model=ChatResponse)
async def doctor_chat(payload: ChatRequest, request: Request):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing in .env")

    _ensure_rate_limit(request)
    patient_context = _sanitize_patient_context(
        payload.patient_age,
        payload.patient_weight,
        payload.allergies,
        payload.current_medications,
    )
    prompt = _build_conversation_text(payload.messages, payload.message, payload.language, patient_context)
    response = _generate_gemini_content(prompt)

    raw_text = _extract_text_from_response(response)
    if not raw_text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    if not validate_response(raw_text):
        raise HTTPException(status_code=502, detail="Gemini returned an unsafe response")

    reply, diagnosis = _extract_reply_and_diagnosis(raw_text)
    reply = _append_safety_disclaimer(reply)
    return JSONResponse({"reply": reply, "diagnosis": diagnosis}, headers=_common_headers(request))


@router.post("/api/doctor/chat/stream")
async def doctor_chat_stream(payload: ChatRequest, request: Request):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing in .env")

    _ensure_rate_limit(request)
    patient_context = _sanitize_patient_context(
        payload.patient_age,
        payload.patient_weight,
        payload.allergies,
        payload.current_medications,
    )
    prompt = _build_conversation_text(payload.messages, payload.message, payload.language, patient_context)
    response = _generate_gemini_content(prompt)
    raw_text = _extract_text_from_response(response)
    if not raw_text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    if not validate_response(raw_text):
        raise HTTPException(status_code=502, detail="Gemini returned an unsafe response")

    reply, diagnosis = _extract_reply_and_diagnosis(raw_text)
    reply = _append_safety_disclaimer(reply)

    async def generate():
        try:
            for chunk_text in _chunk_text(reply):
                yield f"data: {json.dumps({'chunk': chunk_text})}\n\n"
            if diagnosis.get("items"):
                yield f"data: {json.dumps({'chunk': f'|||DIAGNOSIS|||{json.dumps(diagnosis, separators=(',', ':'))}|||END|||'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_stream_headers(request))


@router.post("/api/doctor/summary", response_model=SummaryResponse)
async def doctor_summary(payload: SummaryRequest, request: Request):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing in .env")

    _ensure_rate_limit(request)
    patient_context = _sanitize_patient_context(
        payload.patient_age,
        payload.patient_weight,
        payload.allergies,
        payload.current_medications,
    )
    prompt = _build_summary_prompt(payload.messages, payload.language, patient_context)
    response = _generate_gemini_content(prompt)
    raw_text = _extract_text_from_response(response)
    if not raw_text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    if not validate_response(raw_text):
        raise HTTPException(status_code=502, detail="Gemini returned an unsafe response")

    summary, _diagnosis = _extract_reply_and_diagnosis(raw_text)
    return JSONResponse({"summary": summary}, headers=_common_headers(request))


@router.post("/api/doctor/medicine-info")
async def doctor_medicine_info(payload: MedicineInfoRequest, request: Request):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing in .env")

    _ensure_rate_limit(request)
    medicine_name = _sanitize_text(payload.medicine_name)
    if not medicine_name:
        raise HTTPException(status_code=400, detail="medicine_name is required")

    patient_context = _sanitize_patient_context(
        payload.patient_age,
        payload.patient_weight,
        payload.allergies,
        payload.current_medications,
    )

    prompt = f"""Provide information about the medicine '{medicine_name}'.

PATIENT CONTEXT:
{chr(10).join(_patient_context_lines(patient_context))}

{AGE_SAFETY_RULES.strip()}

Include:
1. What it's used for (conditions treated)
2. Dosage guidance only if BOTH patient_age and patient_weight are provided; otherwise say age and weight are needed for safe dosing
3. Common side effects
4. When to see a doctor
5. Warnings (interactions, allergies)

Be accurate and up-to-date with current medical guidelines.
Do not invent information. If unsure, say "Consult your doctor."

Return only JSON with fields: uses, dosage, side_effects, warnings, see_doctor"""

    response = _generate_gemini_content(prompt)
    raw_text = _extract_text_from_response(response)
    if not validate_response(raw_text):
        raise HTTPException(status_code=502, detail="Gemini returned an unsafe response")
    data = _extract_json_object(raw_text)
    return JSONResponse(data, headers=_common_headers(request))


@router.get("/ai-doctor-live")
async def ai_doctor_live_page(request: Request):
    response = render_template(templates, request, "doctor.html")
    response.headers["Cache-Control"] = "no-store"
    return response
