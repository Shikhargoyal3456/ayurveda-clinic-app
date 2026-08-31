import json
import os
import re
from collections import defaultdict
from time import time

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.auth import ensure_csrf_token, pop_flash, verify_csrf
from services.ai_provider import build_gemini_part, generate_gemini_content, is_gemini_configured
from shared.template_engine import render_template, templates


load_dotenv()

router = APIRouter(tags=["patient-tools"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
MAX_TEXT_CHARS = 2500
MAX_IMAGE_BYTES = 8 * 1024 * 1024
JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

SYMPTOM_ANALYZER_PROMPT = """You are Dr. Kash, an AI symptom checker. Analyze the patient's symptoms and provide:

1. Possible conditions (2-3) with confidence percentages
2. Urgency level: EMERGENCY, URGENT, or ROUTINE
3. Recommended actions (specific next steps)
4. When to see a doctor
5. Home care advice

Be conservative. When in doubt, advise seeing a doctor.
Flag emergencies immediately if symptoms suggest chest pain, difficulty breathing, severe bleeding, stroke signs, or loss of consciousness.

Return only JSON with this shape:
{
  "summary": "brief patient-friendly summary",
  "conditions": [{"name": "Condition", "confidence": 65, "reason": "why it fits"}],
  "urgency": "EMERGENCY",
  "actions": ["step 1", "step 2"],
  "see_doctor_when": ["warning sign 1", "warning sign 2"],
  "home_care": ["tip 1", "tip 2"],
  "disclaimer": "short safety disclaimer"
}

Do not include markdown. Do not include text outside JSON."""


DIET_ANALYZER_PROMPT = """You are Dr. Kash, an AI nutritionist. Analyze the patient's meal and provide:

1. Calorie estimate (range)
2. Nutritional quality (Excellent/Good/Needs Improvement)
3. Health impact
4. Specific concerns (high sugar, high fat, low protein, low fiber, high sodium, etc.)
5. Recommendations for next meal

Be constructive and encouraging, not judgmental.
Focus on positive changes rather than criticizing.

Return only JSON with this shape:
{
  "summary": "brief patient-friendly summary",
  "calorie_estimate": "approximate range",
  "nutritional_quality": "Good",
  "health_impact": "short explanation",
  "nutritional_breakdown": ["protein: ...", "carbs: ...", "fats: ..."],
  "concerns": ["concern 1", "concern 2"],
  "recommendations": ["next meal idea 1", "next meal idea 2"],
  "disclaimer": "short nutrition disclaimer"
}

Do not include markdown. Do not include text outside JSON."""


class RateLimiter:
    def __init__(self, max_requests: int = 25, window_seconds: int = 3600):
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


def _sanitize_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT_CHARS]


def _pick_models() -> list[str]:
    models: list[str] = []
    for candidate in (GEMINI_MODEL, DEFAULT_GEMINI_MODEL, FALLBACK_GEMINI_MODEL):
        model_name = (candidate or "").strip()
        if model_name and model_name not in models:
            models.append(model_name)
    return models


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ensure_rate_limit(request: Request) -> None:
    if not rate_limiter.check(_client_ip(request)):
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


def _sanitize_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _sanitize_text(item)
        if text:
            cleaned.append(text)
    return cleaned


def _normalize_symptom_payload(payload: dict) -> dict:
    conditions = payload.get("conditions")
    if not isinstance(conditions, list):
        conditions = []
    normalized_conditions = []
    for item in conditions[:3]:
        if not isinstance(item, dict):
            continue
        name = _sanitize_text(item.get("name", "Possible condition"))
        confidence = max(0, min(100, int(float(item.get("confidence", 0) or 0))))
        reason = _sanitize_text(item.get("reason", ""))
        normalized_conditions.append({"name": name, "confidence": confidence, "reason": reason})

    return {
        "summary": _sanitize_text(payload.get("summary", "")),
        "conditions": normalized_conditions,
        "urgency": _sanitize_text(payload.get("urgency", "ROUTINE")).upper() or "ROUTINE",
        "actions": _sanitize_list(payload.get("actions")),
        "see_doctor_when": _sanitize_list(payload.get("see_doctor_when")),
        "home_care": _sanitize_list(payload.get("home_care")),
        "disclaimer": _sanitize_text(payload.get("disclaimer", "AI guidance only — please consult a qualified doctor for diagnosis and treatment.")),
    }


def _normalize_diet_payload(payload: dict) -> dict:
    return {
        "summary": _sanitize_text(payload.get("summary", "")),
        "calorie_estimate": _sanitize_text(payload.get("calorie_estimate", "")),
        "nutritional_quality": _sanitize_text(payload.get("nutritional_quality", "Needs Improvement")),
        "health_impact": _sanitize_text(payload.get("health_impact", "")),
        "nutritional_breakdown": _sanitize_list(payload.get("nutritional_breakdown")),
        "concerns": _sanitize_list(payload.get("concerns")),
        "recommendations": _sanitize_list(payload.get("recommendations")),
        "disclaimer": _sanitize_text(payload.get("disclaimer", "AI nutrition guidance only — please consult a qualified clinician or dietitian for medical dietary advice.")),
    }


def _diet_image_fallback_payload(has_description: bool) -> dict:
    summary = (
        "We could not confidently read the uploaded meal photo, so this assessment is based on your written meal description only."
        if has_description
        else "We could not confidently identify the meal from the uploaded photo. Please upload a clearer image or add a short meal description."
    )
    recommendations = (
        ["Retake the meal photo in good lighting.", "Add a quick written description for a more accurate nutrition estimate."]
        if not has_description
        else ["Retake the meal photo in good lighting if you want image-based analysis.", "Use the written nutrition guidance below as a general estimate."]
    )
    return {
        "summary": summary,
        "calorie_estimate": "Not enough visual detail",
        "nutritional_quality": "Needs Review",
        "health_impact": "A clearer image or short description is needed for a reliable meal assessment.",
        "nutritional_breakdown": [],
        "concerns": ["Uploaded meal image could not be interpreted confidently."],
        "recommendations": recommendations,
        "disclaimer": "AI nutrition guidance only — please consult a qualified clinician or dietitian for medical dietary advice.",
    }


def _generate_content(parts: str | list[object]) -> str:
    try:
        return generate_gemini_content(
            parts,
            model_name=GEMINI_MODEL,
            model_candidates=_pick_models(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc


def _common_page_context(request: Request) -> dict[str, object]:
    return {
        "request": request,
        "csrf_token": ensure_csrf_token(request),
        "flash": pop_flash(request),
    }


@router.get("/patient/symptom-analyzer")
async def patient_symptom_analyzer_page(request: Request):
    context = _common_page_context(request)
    context["simple_nav"] = "tools"
    context["page_hint"] = "AI symptom checker for everyday health guidance"
    return render_template(templates, request, "patient_symptom_analyzer.html", context)


@router.get("/patient/diet-analyzer")
async def patient_diet_analyzer_page(request: Request):
    context = _common_page_context(request)
    context["simple_nav"] = "tools"
    context["page_hint"] = "AI meal analysis and nutrition guidance"
    return render_template(templates, request, "patient_diet_analyzer.html", context)


@router.post("/api/patient/symptom-analyze")
async def patient_symptom_analyze(
    request: Request,
    symptoms: str = Form(...),
    _: None = Depends(verify_csrf),
):
    if not is_gemini_configured():
        raise HTTPException(status_code=500, detail="Vertex AI Gemini is not configured. Set VERTEX_AI_PROJECT and authenticate with ADC.")

    _ensure_rate_limit(request)
    cleaned = _sanitize_text(symptoms)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Symptoms are required.")

    prompt = f"""{SYMPTOM_ANALYZER_PROMPT}

Patient symptoms:
{cleaned}
"""
    payload = _extract_json_object(_generate_content(prompt))
    return JSONResponse(_normalize_symptom_payload(payload))


@router.post("/api/patient/diet-analyze")
async def patient_diet_analyze(
    request: Request,
    meal_description: str = Form(""),
    food_image: UploadFile | None = File(default=None),
    _: None = Depends(verify_csrf),
):
    if not is_gemini_configured():
        raise HTTPException(status_code=500, detail="Vertex AI Gemini is not configured. Set VERTEX_AI_PROJECT and authenticate with ADC.")

    _ensure_rate_limit(request)
    cleaned = _sanitize_text(meal_description)
    if not cleaned and food_image is None:
        raise HTTPException(status_code=400, detail="Provide a meal description or upload a food photo.")

    parts: list[object] = [DIET_ANALYZER_PROMPT]
    if cleaned:
        parts.append(f"Meal description: {cleaned}")

    if food_image is not None:
        file_bytes = await food_image.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        if len(file_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Image must be 8 MB or smaller.")
        mime_type = (food_image.content_type or "").strip().lower()
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail="Use a JPG, PNG, or WEBP image.")
        parts.append(build_gemini_part(file_bytes, mime_type))
        if not cleaned:
            parts.append("The patient uploaded only a food photo. Infer the likely meal content conservatively and state uncertainty inside the JSON summary if needed.")
    try:
        payload = _extract_json_object(_generate_content(parts))
        return JSONResponse(_normalize_diet_payload(payload))
    except HTTPException:
        if food_image is None:
            raise
        if cleaned:
            retry_prompt = f"""{DIET_ANALYZER_PROMPT}

Meal description: {cleaned}

Note: The uploaded meal image could not be analyzed confidently. Base the response on the written meal description only, and mention that limitation briefly in the JSON summary.
"""
            payload = _extract_json_object(_generate_content(retry_prompt))
            normalized = _normalize_diet_payload(payload)
            if normalized["summary"]:
                normalized["summary"] = f"{normalized['summary']} Photo analysis was unavailable, so this assessment is based on the meal description."
            else:
                normalized["summary"] = _diet_image_fallback_payload(True)["summary"]
            return JSONResponse(normalized)
        return JSONResponse(_diet_image_fallback_payload(False))
