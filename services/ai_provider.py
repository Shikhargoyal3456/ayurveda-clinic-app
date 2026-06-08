import json
import logging
import os
import re
import time
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterator, List
from threading import Lock

from google import genai
from google.genai import types

from app.config import BASE_DIR, load_dotenv, settings
from services.cache_service import cache_result


load_dotenv(BASE_DIR / ".env")


class AIProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"


logger = logging.getLogger("ai_provider")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
VERTEX_AI_PROJECT = os.getenv("VERTEX_AI_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "")).strip()
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1").strip() or "us-central1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
_AI_SPEND_LOCK = Lock()
_AI_SPEND_LEDGER = BASE_DIR / "logs" / "ai_spend_guard.json"
_GENAI_CLIENT_LOCK = Lock()
_GENAI_CLIENT: genai.Client | None = None

_PHI_FIELDS = {
    "patient_name",
    "name",
    "full_name",
    "phone",
    "mobile",
    "email",
    "address",
    "aadhar",
    "dob",
    "patient_id",
}

_AI_BUDGET_ERROR_MARKERS = (
    "spend cap",
    "daily spend cap",
    "daily budget",
    "quota",
    "resource exhausted",
    "billing",
)


def _cacheable_prompt_value(value: str | List[Dict[str, str]]) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value or "")


def _load_spend_state() -> dict[str, Any]:
    if not _AI_SPEND_LEDGER.exists():
        return {"date": "", "estimated_spend_usd": 0.0, "calls": 0}
    try:
        return json.loads(_AI_SPEND_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"date": "", "estimated_spend_usd": 0.0, "calls": 0}


def _enforce_ai_budget() -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    estimated_call_cost = max(0.0, float(getattr(settings, "ai_max_cost_per_call_usd", 0.0)))
    daily_budget = max(0.0, float(getattr(settings, "ai_daily_budget_usd", 0.0)))
    if not daily_budget:
        return

    with _AI_SPEND_LOCK:
        state = _load_spend_state()
        if state.get("date") != today:
            state = {"date": today, "estimated_spend_usd": 0.0, "calls": 0}
        projected_spend = float(state.get("estimated_spend_usd", 0.0)) + estimated_call_cost
        if projected_spend > daily_budget:
            raise RuntimeError("AI daily spend cap reached. Please try again later.")
        state["estimated_spend_usd"] = round(projected_spend, 4)
        state["calls"] = int(state.get("calls", 0) or 0) + 1
        _AI_SPEND_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        _AI_SPEND_LEDGER.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def is_ai_budget_error(exc: Exception) -> bool:
    message = str(exc or "").strip().lower()
    return any(marker in message for marker in _AI_BUDGET_ERROR_MARKERS)


def ai_budget_fallback_message() -> str:
    return "AI service is currently unavailable. Please try again later or use manual entry."


def is_gemini_configured() -> bool:
    return bool(VERTEX_AI_PROJECT)


def _get_genai_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is not None:
        return _GENAI_CLIENT
    if not VERTEX_AI_PROJECT:
        raise RuntimeError("VERTEX_AI_PROJECT is not configured.")
    with _GENAI_CLIENT_LOCK:
        if _GENAI_CLIENT is None:
            _GENAI_CLIENT = genai.Client(
                vertexai=True,
                project=VERTEX_AI_PROJECT,
                location=VERTEX_AI_LOCATION,
                http_options=types.HttpOptions(api_version="v1"),
            )
        return _GENAI_CLIENT


GEMINI_API_KEY = ""


def build_gemini_part(data: bytes, mime_type: str) -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def _model_candidates(explicit_model: str | None = None, model_candidates: list[str] | None = None) -> list[str]:
    models: list[str] = []
    for candidate in [explicit_model, *(model_candidates or []), GEMINI_MODEL]:
        model_name = str(candidate or "").strip()
        if model_name and model_name not in models:
            models.append(model_name)
    return models or [GEMINI_MODEL]


def generate_gemini_content(
    contents: str | list[Any],
    *,
    system_instruction: str = "",
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
    model_name: str | None = None,
    model_candidates: list[str] | None = None,
) -> str:
    if not is_gemini_configured():
        raise RuntimeError("Vertex AI Gemini is not configured.")
    _enforce_ai_budget()
    client = _get_genai_client()

    last_error: Exception | None = None
    for candidate in _model_candidates(model_name, model_candidates):
        try:
            config_kwargs: dict[str, Any] = {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "system_instruction": system_instruction or None,
                "http_options": types.HttpOptions(timeout=AI_TIMEOUT * 1000),
            }
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type
            response = client.models.generate_content(
                model=candidate,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = str(getattr(response, "text", "") or "").strip()
            if text:
                return text
            raise RuntimeError(f"Gemini returned an empty response for model {candidate}.")
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise RuntimeError(f"Vertex AI Gemini request failed: {last_error}") from last_error
    raise RuntimeError("Vertex AI Gemini request failed.")


def generate_gemini_content_stream(
    contents: str | list[Any],
    *,
    system_instruction: str = "",
    temperature: float = 0.3,
    max_output_tokens: int = 2048,
    model_name: str | None = None,
    model_candidates: list[str] | None = None,
) -> Iterator[str]:
    if not is_gemini_configured():
        raise RuntimeError("Vertex AI Gemini is not configured.")
    _enforce_ai_budget()
    client = _get_genai_client()

    last_error: Exception | None = None
    for candidate in _model_candidates(model_name, model_candidates):
        try:
            config_kwargs: dict[str, Any] = {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "system_instruction": system_instruction or None,
                "http_options": types.HttpOptions(timeout=AI_TIMEOUT * 1000),
            }
            stream = client.models.generate_content_stream(
                model=candidate,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            yielded = False
            for chunk in stream:
                text = str(getattr(chunk, "text", "") or "")
                if text:
                    yielded = True
                    yield text
            if yielded:
                return
            raise RuntimeError(f"Gemini stream returned no content for model {candidate}.")
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise RuntimeError(f"Vertex AI Gemini stream failed: {last_error}") from last_error
    raise RuntimeError("Vertex AI Gemini stream failed.")


def chat_with_gemini(
    system_prompt: str | List[Dict[str, str]],
    user_prompt: str = "",
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> str:
    """
    Call Gemini via Vertex AI. Returns response text.
    Raises RuntimeError if the call fails.
    """
    if isinstance(system_prompt, list):
        prompt_parts = []
        for message in system_prompt:
            role = (message.get("role") or "").strip()
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        system_prompt = ""
        user_prompt = "\n\n".join(prompt_parts)

    start_time = time.time()
    text = generate_gemini_content(
        user_prompt,
        system_instruction=system_prompt,
        temperature=temperature,
        response_mime_type=response_mime_type,
        max_output_tokens=max_output_tokens,
    )
    elapsed = time.time() - start_time
    logger.info("Gemini responded in %.2fs using model=%s", elapsed, GEMINI_MODEL)
    return text.strip()


def stream_with_gemini(
    system_prompt: str | List[Dict[str, str]],
    user_prompt: str = "",
    temperature: float = 0.3,
    max_output_tokens: int = 2048,
) -> Iterator[str]:
    if isinstance(system_prompt, list):
        prompt_parts = []
        for message in system_prompt:
            role = (message.get("role") or "").strip()
            content = (message.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        system_prompt = ""
        user_prompt = "\n\n".join(prompt_parts)

    yield from generate_gemini_content_stream(
        user_prompt,
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


def chat_with_groq(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """
    Call Groq chat completions. Returns response text.
    Raises RuntimeError if Groq is not configured or the SDK is not installed.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    _enforce_ai_budget()

    try:
        import groq
    except ImportError as exc:
        raise RuntimeError("Groq SDK is not installed. Install requirements.txt in the app runtime.") from exc

    client = groq.Groq(api_key=GROQ_API_KEY)
    start_time = time.time()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        timeout=AI_TIMEOUT,
    )
    elapsed = time.time() - start_time
    logger.info("Groq responded in %.2fs using model=%s", elapsed, GROQ_MODEL)

    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("Groq returned an empty response.")
    return content.strip()


def chat_with_fallback(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> tuple[str, AIProvider]:
    """
    Use the configured remote AI provider without falling back to Ollama.
    Gemini is preferred when configured; Groq is used as the secondary provider.
    """
    if is_gemini_configured():
        return chat_with_gemini(
            system_prompt,
            user_prompt,
            temperature,
            response_mime_type,
            max_output_tokens,
        ), AIProvider.GEMINI
    if GROQ_API_KEY:
        return chat_with_groq(system_prompt, user_prompt, temperature), AIProvider.GROQ
    raise RuntimeError("Neither Vertex AI Gemini nor Groq is configured. AI provider is unavailable.")


@cache_result(ttl=3600)
async def call_ai_text_cached(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> dict[str, str]:
    text, provider = await asyncio.to_thread(
        chat_with_fallback,
        system_prompt,
        user_prompt,
        temperature,
        response_mime_type,
        max_output_tokens,
    )
    return {"text": text, "provider": provider.value}


async def call_gemini(
    prompt: str,
    *,
    system_prompt: str = "You are a careful healthcare AI assistant. Return grounded, structured output.",
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> str:
    """Async compatibility wrapper for Gemini-preferred text generation."""
    result = await call_ai_text_cached(
        _cacheable_prompt_value(system_prompt),
        _cacheable_prompt_value(prompt),
        temperature,
        response_mime_type,
        max_output_tokens,
    )
    return str(result.get("text") or "").strip()


async def call_gemini_with_fallback(
    prompt: str,
    *,
    system_prompt: str = "You are a careful healthcare AI assistant. Return grounded, structured output.",
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> str:
    try:
        return await call_gemini(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_mime_type=response_mime_type,
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        if is_ai_budget_error(exc):
            return ai_budget_fallback_message()
        raise


async def call_ai_with_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    simpler_user_prompt: str | None = None,
    temperature: float = 0.3,
    response_mime_type: str | None = None,
    max_output_tokens: int = 2048,
) -> dict[str, str]:
    try:
        return await call_ai_text_cached(
            _cacheable_prompt_value(system_prompt),
            _cacheable_prompt_value(user_prompt),
            temperature,
            response_mime_type,
            max_output_tokens,
        )
    except Exception as primary_exc:
        logger.warning("Primary AI call failed, retrying with simpler prompt: %s", primary_exc)
        if not simpler_user_prompt or simpler_user_prompt.strip() == str(user_prompt).strip():
            raise
        return await call_ai_text_cached(
            _cacheable_prompt_value(system_prompt),
            _cacheable_prompt_value(simpler_user_prompt),
            min(temperature, 0.2),
            response_mime_type,
            max_output_tokens,
        )


async def call_ai_json_with_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    simpler_user_prompt: str | None = None,
    temperature: float = 0.3,
    max_output_tokens: int = 2048,
) -> tuple[dict[str, Any], str]:
    last_error: Exception | None = None
    for prompt in [user_prompt, simpler_user_prompt]:
        if not prompt:
            continue
        try:
            result = await call_ai_text_cached(
                _cacheable_prompt_value(system_prompt),
                _cacheable_prompt_value(prompt),
                temperature if prompt == user_prompt else min(temperature, 0.2),
                "application/json",
                max_output_tokens,
            )
            return parse_json_response(result["text"]), result["provider"]
        except Exception as exc:
            last_error = exc
            logger.warning("AI JSON call failed for current prompt: %s", exc)
    if last_error is not None:
        raise last_error
    raise RuntimeError("AI JSON call could not be attempted.")


def parse_json_response(raw: str) -> dict:
    """
    Strip markdown code fences and parse JSON.
    Handles ```json ... ``` and ``` ... ``` wrapping.
    Raises ValueError with clear message if parsing fails.
    """
    cleaned = (raw or "").strip()

    if cleaned.startswith("```"):
        fenced_parts = cleaned.split("```")
        if len(fenced_parts) > 1:
            cleaned = fenced_parts[1].strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON. Raw response: {raw[:200]}...") from exc


def _strip_json_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _sanitize_case_data(case_data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in (case_data or {}).items() if str(key).lower() not in _PHI_FIELDS}


def _safe_json_load(raw: str) -> dict[str, Any]:
    return json.loads(_strip_json_fences(raw))


def _present_text(value: Any, fallback: str = "Not specified") -> str:
    text = str(value or "").strip()
    return text or fallback


def get_prescription_sync(case_text: str) -> str:
    """Return a prescription-style AI response without raising provider errors."""
    prompt = (
        "Create a concise, doctor-facing prescription draft from this case summary. "
        "Explain the likely assessment, practical next steps, medication/herb considerations when appropriate, "
        "and a short safety note. Keep it clinically cautious and clearly marked as doctor review required.\n\n"
        f"Case summary:\n{str(case_text or '').strip()}"
    )
    try:
        answer, _provider = chat_with_fallback(
            "You are a careful clinical assistant helping draft prescriptions for doctor review.",
            prompt,
            temperature=0.2,
            max_output_tokens=1200,
        )
        return answer
    except Exception as exc:
        logger.exception("AI prescription call failed: %s", exc)
        simpler_prompt = (
            "Create a brief doctor-review prescription draft using only the core complaint and immediate next steps.\n\n"
            f"Case summary:\n{str(case_text or '').strip()[:1200]}"
        )
        answer, _provider = chat_with_fallback(
            "You are a careful clinical assistant helping draft prescriptions for doctor review.",
            simpler_prompt,
            temperature=0.1,
            max_output_tokens=800,
        )
        return answer


async def get_prescription(case_text: str) -> str:
    return await asyncio.to_thread(get_prescription_sync, case_text)


def _json_case_data(case_data: dict[str, Any]) -> str:
    return json.dumps(case_data, ensure_ascii=False, indent=2)


def _safe_case_field(case_data: dict[str, Any], key: str, fallback: str = "") -> str:
    return str(case_data.get(key, fallback) or fallback).strip()


def _stringify_case_query(case_data: dict[str, Any]) -> str:
    parts = [
        _safe_case_field(case_data, "chief_complaint"),
        _safe_case_field(case_data, "symptoms"),
        _safe_case_field(case_data, "diagnosis"),
        _safe_case_field(case_data, "notes"),
        _safe_case_field(case_data, "query_text"),
    ]
    return "\n".join(part for part in parts if part).strip() or "General clinical presentation."


def _render_structured_prescription(payload: dict[str, Any], mode: str) -> str:
    if mode == "modern":
        diagnosis = payload.get("diagnosis") or {}
        medications = payload.get("medications") or []
        investigations = payload.get("investigations") or []
        referral = payload.get("referral") or {}
        advice = payload.get("advice") or []
        red_flags = payload.get("red_flags") or []

        lines = [
            f"Primary Diagnosis: {diagnosis.get('primary', 'Not specified')}",
        ]
        if diagnosis.get("icd11_code"):
            lines.append(f"ICD-11 Code: {diagnosis['icd11_code']}")
        if diagnosis.get("differential"):
            lines.append("Differential Diagnosis:")
            lines.extend(f"- {item}" for item in diagnosis["differential"])
        if medications:
            lines.append("Medications:")
            for item in medications:
                parts = [
                    str(item.get("generic_name", "")).strip(),
                    str(item.get("dosage", "")).strip(),
                    str(item.get("frequency", "")).strip(),
                    str(item.get("duration", "")).strip(),
                    str(item.get("route", "")).strip(),
                ]
                lines.append(f"- {', '.join(part for part in parts if part)}")
        if investigations:
            lines.append("Investigations Suggested:")
            for item in investigations:
                reason = str(item.get("reason", "")).strip()
                urgency = str(item.get("urgency", "")).strip()
                suffix = f" ({', '.join(part for part in [reason, urgency] if part)})" if (reason or urgency) else ""
                lines.append(f"- {str(item.get('test', '')).strip()}{suffix}")
        if referral.get("required"):
            lines.append("Referral:")
            lines.append(
                f"- {str(referral.get('specialty', '')).strip() or 'Specialist review'}"
                + (f": {str(referral.get('reason', '')).strip()}" if referral.get("reason") else "")
            )
        if advice:
            lines.append("Patient Counselling:")
            lines.extend(f"- {item}" for item in advice)
        if red_flags:
            lines.append("Red Flag Symptoms:")
            lines.extend(f"- {item}" for item in red_flags)
        return "\n".join(lines).strip()

    diagnosis = payload.get("diagnosis") or {}
    nidana = payload.get("nidana") or {}
    medicines = payload.get("medicines") or []
    diet = payload.get("dietary_advice") or {}
    lifestyle = payload.get("lifestyle_advice") or []
    panchakarma = payload.get("panchakarma") or {}

    lines = [
        f"Nidana: {diagnosis.get('english', 'Not specified')}",
    ]
    if diagnosis.get("sanskrit"):
        lines.append(f"Ayurvedic Diagnosis: {diagnosis['sanskrit']}")
    if diagnosis.get("dosha_involvement"):
        lines.append(f"Dosha Involvement: {diagnosis['dosha_involvement']}")
    if diagnosis.get("dhatu_involvement"):
        lines.append(f"Dhatu Involvement: {diagnosis['dhatu_involvement']}")
    if diagnosis.get("sroto_involvement"):
        lines.append(f"Sroto Involvement: {diagnosis['sroto_involvement']}")
    if nidana.get("probable_cause"):
        lines.append(f"Probable Cause: {nidana['probable_cause']}")
    if medicines:
        lines.append("Chikitsa:")
        for item in medicines:
            name = str(item.get("name", "")).strip() or str(item.get("sanskrit_name", "")).strip()
            parts = [
                str(item.get("dosage", "")).strip(),
                str(item.get("anupana", "")).strip(),
                str(item.get("duration", "")).strip(),
                str(item.get("timing", "")).strip(),
            ]
            lines.append(f"- {name}: {', '.join(part for part in parts if part)}")
    pathya = diet.get("pathya") or []
    apathya = diet.get("apathya") or []
    if pathya or apathya:
        lines.append("Pathya-Apathya:")
        lines.extend(f"- Pathya: {item}" for item in pathya)
        lines.extend(f"- Apathya: {item}" for item in apathya)
    if lifestyle:
        lines.append("Lifestyle Advice:")
        lines.extend(f"- {item}" for item in lifestyle)
    if panchakarma.get("recommended"):
        procedures = ", ".join(str(item).strip() for item in (panchakarma.get("procedures") or []) if str(item).strip())
        lines.append(f"Panchakarma: {procedures or 'Recommended'}")
    return "\n".join(lines).strip()


def _specialty_prompt(mode: str) -> tuple[str, str]:
    prompts = {
        "modern": (
            "You are a Modern Medicine doctor (MBBS/MD). Generate an evidence-based prescription draft for doctor review.",
            "## Diagnosis\n- Primary diagnosis\n- ICD-11 code if appropriate\n- Differential diagnoses\n\n"
            "## Investigations\n- Essential tests only\n\n"
            "## Medications\n| Medicine | Dosage | Frequency | Duration | Route |\n|---|---|---|---|---|\n\n"
            "## Advice\n- Lifestyle modifications\n- Diet recommendations\n- Warning signs\n\n"
            "## Follow-up\n- Review timeline and precautions",
        ),
        "homeopathy": (
            "You are a senior homeopathy doctor (BHMS). Generate a classical homeopathy prescription draft for doctor review.",
            "## Constitutional Assessment\n- Core symptom picture\n- Miasm / modality clues\n\n"
            "## Remedy Options\n| Remedy | Potency | Frequency | Duration |\n|---|---|---|---|\n\n"
            "## Supportive Advice\n- Diet and lifestyle guidance\n\n"
            "## Follow-up\n- Review plan and red flags",
        ),
        "physiotherapy": (
            "You are a senior physiotherapist (BPT/MPT). Generate a rehabilitation-oriented prescription draft for doctor review.",
            "## Clinical Assessment\n- Working diagnosis\n- Functional limitation\n\n"
            "## Treatment Plan\n| Exercise / Modality | Dosage | Frequency | Duration |\n|---|---|---|---|\n\n"
            "## Home Program\n- Daily exercise advice\n- Activity modification\n\n"
            "## Follow-up\n- Reassessment timeline and warning signs",
        ),
        "dentistry": (
            "You are a senior dentist (BDS/MDS). Generate a dental prescription draft for doctor review.",
            "## Dental Diagnosis\n- Likely diagnosis\n- Tooth / region involved\n\n"
            "## Medications / Procedures\n| Item | Dosage / Plan | Frequency | Duration |\n|---|---|---|---|\n\n"
            "## Instructions\n- Oral hygiene advice\n- Food precautions\n\n"
            "## Follow-up\n- Review plan and urgent warning signs",
        ),
        "general": (
            "You are a careful clinical assistant. Generate a safe, general prescription draft for doctor review.",
            "## Assessment\n- Working diagnosis\n- Key concerns\n\n"
            "## Plan\n| Item | Dosage / Advice | Frequency | Duration |\n|---|---|---|---|\n\n"
            "## Advice\n- Lifestyle and follow-up recommendations",
        ),
    }
    return prompts.get(mode, prompts["general"])


def _normalize_prescription_medicines(payload: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if mode == "modern":
        medications = payload.get("medications") or []
        normalized: list[dict[str, Any]] = []
        for item in medications:
            if not isinstance(item, dict):
                continue
            alternatives = item.get("alternatives") if isinstance(item.get("alternatives"), list) else []
            side_effects = item.get("potential_side_effects") if isinstance(item.get("potential_side_effects"), dict) else {}
            normalized.append(
                {
                    "name": str(item.get("generic_name") or item.get("name") or "").strip(),
                    "dosage": str(item.get("dosage") or "").strip(),
                    "frequency": str(item.get("frequency") or "").strip(),
                    "duration": str(item.get("duration") or "").strip(),
                    "timing": str(item.get("timing") or item.get("frequency") or "").strip(),
                    "route": str(item.get("route") or "").strip(),
                    "detailed_info": {
                        "benefits": [str(value).strip() for value in (item.get("benefits") or []) if str(value).strip()],
                        "side_effects": {
                            "common": [str(value).strip() for value in (side_effects.get("common") or []) if str(value).strip()],
                            "serious": [str(value).strip() for value in (side_effects.get("serious") or []) if str(value).strip()],
                            "what_to_do": str(side_effects.get("what_to_do") or "").strip(),
                        },
                        "alternatives": [
                            {
                                "name": str(alt.get("name") or "").strip(),
                                "composition": str(alt.get("composition") or "").strip(),
                                "price_savings": alt.get("price_savings", 0),
                                "reason": str(alt.get("reason") or "").strip(),
                            }
                            for alt in alternatives
                            if isinstance(alt, dict) and str(alt.get("name") or "").strip()
                        ],
                        "dosage_info": {
                            "adult_dosage": str(item.get("dosage") or "").strip(),
                            "max_daily": str(item.get("max_daily") or "").strip(),
                            "timing": str(item.get("timing") or item.get("frequency") or "").strip(),
                            "with_food": str(item.get("with_food") or "").strip(),
                        },
                        "precautions": [str(value).strip() for value in (item.get("precautions") or []) if str(value).strip()],
                        "confidence": int(payload.get("confidence_score", 0) or 0),
                        "ai_generated": True,
                    },
                }
            )
        return normalized

    medicines = payload.get("medicines") or []
    normalized = []
    for item in medicines:
        if not isinstance(item, dict):
            continue
        alternatives = item.get("alternatives") if isinstance(item.get("alternatives"), list) else []
        side_effects = item.get("potential_side_effects") if isinstance(item.get("potential_side_effects"), dict) else {}
        normalized.append(
            {
                "name": str(item.get("name") or item.get("sanskrit_name") or "").strip(),
                "dosage": str(item.get("dosage") or "").strip(),
                "frequency": str(item.get("timing") or "").strip(),
                "duration": str(item.get("duration") or "").strip(),
                "timing": str(item.get("timing") or "").strip(),
                "anupana": str(item.get("anupana") or "").strip(),
                "detailed_info": {
                    "benefits": [str(value).strip() for value in (item.get("benefits") or []) if str(value).strip()],
                    "side_effects": {
                        "common": [str(value).strip() for value in (side_effects.get("common") or []) if str(value).strip()],
                        "serious": [str(value).strip() for value in (side_effects.get("serious") or []) if str(value).strip()],
                        "what_to_do": str(side_effects.get("what_to_do") or "").strip(),
                    },
                    "alternatives": [
                        {
                            "name": str(alt.get("name") or "").strip(),
                            "composition": str(alt.get("composition") or "").strip(),
                            "price_savings": alt.get("price_savings", 0),
                            "reason": str(alt.get("reason") or "").strip(),
                        }
                        for alt in alternatives
                        if isinstance(alt, dict) and str(alt.get("name") or "").strip()
                    ],
                    "dosage_info": {
                        "adult_dosage": str(item.get("dosage") or "").strip(),
                        "max_daily": str(item.get("max_daily") or "").strip(),
                        "timing": str(item.get("timing") or "").strip(),
                        "with_food": str(item.get("with_food") or "").strip(),
                    },
                    "precautions": [str(value).strip() for value in (item.get("precautions") or []) if str(value).strip()],
                    "confidence": int(payload.get("confidence_score", 0) or 0),
                    "ai_generated": True,
                },
            }
        )
    return normalized


def _call_specialty_prescription(case_data: dict[str, Any], mode: str) -> dict[str, Any]:
    system_prompt, format_block = _specialty_prompt(mode)
    user_prompt = (
        f"CASE DETAILS:\n{_json_case_data(case_data)}\n\n"
        f"Generate the prescription in this format:\n\n{format_block}\n\n"
        "Keep the output concise, practical, and clearly suitable for doctor review."
    )
    try:
        prescription, provider = chat_with_fallback(system_prompt, user_prompt, temperature=0.25, max_output_tokens=1600)
        return {
            "success": True,
            "prescription": prescription,
            "mode": mode,
            "provider": provider.value,
            "references": [],
        }
    except Exception as exc:
        logger.exception("Specialty prescription generation failed for mode=%s: %s", mode, exc)
        simpler_prompt = (
            f"CASE DETAILS:\n{_json_case_data(case_data)}\n\n"
            "Generate a brief doctor-review prescription note with assessment, medicines or remedies, and follow-up."
        )
        prescription, provider = chat_with_fallback(
            system_prompt,
            simpler_prompt,
            temperature=0.1,
            max_output_tokens=1000,
        )
        return {
            "success": True,
            "prescription": prescription,
            "mode": mode,
            "provider": provider.value,
            "references": [],
            "warning": str(exc),
        }


async def get_samhita_context(case_data: dict[str, Any]) -> str:
    from app.rag_engine import get_rag_engine

    safe_data = _sanitize_case_data(case_data)
    query_text = _stringify_case_query(safe_data)

    def _retrieve() -> list[Any]:
        return get_rag_engine().retrieve(query_text, top_k=5)

    try:
        passages = await asyncio.to_thread(_retrieve)
    except Exception as exc:
        logger.warning("Samhita context retrieval failed: %s", exc)
        return "No Samhita context available."

    if not passages:
        return "No Samhita context available."

    return "\n\n".join(
        f"Source: {item.source_file}\nRelevance: {round(float(item.score), 4)}\nText: {str(item.text).strip()}"
        for item in passages
    )


async def _retrieve_samhita_passages(case_data: dict[str, Any]) -> list[Any]:
    from app.rag_engine import get_rag_engine

    safe_data = _sanitize_case_data(case_data)
    query_text = _stringify_case_query(safe_data)
    try:
        return await asyncio.to_thread(lambda: get_rag_engine().retrieve(query_text, top_k=5))
    except Exception as exc:
        logger.warning("Samhita passage retrieval failed: %s", exc)
        return []


async def _get_ayurveda_prescription_impl(case_data: dict[str, Any]) -> dict[str, Any]:
    safe_data = _sanitize_case_data(case_data)
    passages = await _retrieve_samhita_passages(safe_data)
    samhita_context = (
        "\n\n".join(
            f"Source: {item.source_file}\nRelevance: {round(float(item.score), 4)}\nText: {str(item.text).strip()}"
            for item in passages
        )
        if passages
        else "No Samhita context available."
    )
    prompt = f"""
You are a senior Ayurveda physician (BAMS, MD Ayurveda).
Using the case details and Samhita references below, generate a complete prescription.

CASE DETAILS:
- Chief Complaint : {safe_data.get('chief_complaint', safe_data.get('diagnosis', 'Not specified'))}
- Symptoms        : {safe_data.get('symptoms', 'Not specified')}
- Duration        : {safe_data.get('duration', 'Not specified')}
- Patient Age     : {safe_data.get('age', 'Not specified')}
- Patient Gender  : {safe_data.get('gender', 'Not specified')}
- Prakriti        : {safe_data.get('prakriti', 'Not specified')}
- Vikruti         : {safe_data.get('vikruti', safe_data.get('diagnosis', 'Not specified'))}

SAMHITA REFERENCES (use these to justify medicines and dietary advice):
{samhita_context[:4000]}

INSTRUCTIONS:
- Base medicines on Samhita references where possible
- Include Sanskrit names with English transliterations
- Doshas and dhatus must be specific (not generic)
- confidence_score: your honest 0-100 estimate based on how well the case maps to Samhita references
- confidence_reason: one sentence explaining the score

Return ONLY a valid JSON object matching this exact schema:
{{
    "diagnosis": {{
        "sanskrit": "",
        "english": "",
        "dosha_involvement": "",
        "dhatu_involvement": "",
        "sroto_involvement": ""
    }},
    "nidana": {{
        "probable_cause": "",
        "samhita_reference": ""
    }},
    "medicines": [
        {{
            "name": "",
            "sanskrit_name": "",
            "form": "churna|vati|kwatha|asava|ghrita|taila|other",
            "dosage": "",
            "anupana": "",
            "duration": "",
            "timing": "before_meals|after_meals|with_meals|bedtime|as_directed",
            "samhita_reference": "",
            "benefits": [],
            "potential_side_effects": {{
                "common": [],
                "serious": [],
                "what_to_do": ""
            }},
            "precautions": [],
            "interactions": [],
            "alternatives": [
                {{
                    "name": "",
                    "composition": "same/different",
                    "price_savings": 0,
                    "reason": ""
                }}
            ],
            "max_daily": "",
            "with_food": "yes/no/optional"
        }}
    ],
    "panchakarma": {{
        "recommended": false,
        "procedures": []
    }},
    "dietary_advice": {{
        "pathya": [],
        "apathya": []
    }},
    "lifestyle_advice": [],
    "follow_up_days": 7,
    "confidence_score": 0,
    "confidence_reason": ""
}}
"""
    simpler_prompt = f"""
You are a senior Ayurveda physician (BAMS, MD Ayurveda).
The case details may be incomplete. Still produce the best possible structured prescription draft for doctor review.

CASE DETAILS:
{_json_case_data(safe_data)}

SAMHITA REFERENCES:
{samhita_context[:2500]}

Return ONLY valid JSON with these keys:
diagnosis, nidana, medicines, panchakarma, dietary_advice, lifestyle_advice, follow_up_days, confidence_score, confidence_reason
"""

    try:
        result, provider = await call_ai_json_with_retry(
            system_prompt="You are a senior Ayurveda physician creating structured JSON prescriptions for doctor review.",
            user_prompt=prompt,
            simpler_user_prompt=simpler_prompt,
            temperature=0.3,
            max_output_tokens=2000,
        )
        missing = [key for key in ["diagnosis", "medicines", "dietary_advice", "confidence_score"] if key not in result]
        if missing:
            raise RuntimeError(f"Incomplete prescription schema, missing: {missing}")
        return {
            "success": True,
            "prescription": result,
            "rendered_prescription": _render_structured_prescription(result, "ayurveda"),
            "medicines": _normalize_prescription_medicines(result, "ayurveda"),
            "mode": "ayurveda",
            "confidence": result.get("confidence_score", 70),
            "references": [item.source_file for item in passages],
            "provider": provider,
        }
    except Exception as exc:
        logger.exception("Ayurveda prescription generation failed: %s", exc)
        raise RuntimeError(f"AI Ayurveda prescription generation failed: {exc}") from exc


async def _get_modern_prescription_impl(case_data: dict[str, Any]) -> dict[str, Any]:
    safe_data = _sanitize_case_data(case_data)
    prompt = f"""
You are a qualified Modern Medicine physician (MBBS/MD).
Using the case details below, generate a complete clinical prescription.

CASE DETAILS:
- Chief Complaint : {safe_data.get('chief_complaint', safe_data.get('diagnosis', 'Not specified'))}
- Symptoms        : {safe_data.get('symptoms', 'Not specified')}
- Duration        : {safe_data.get('duration', 'Not specified')}
- Patient Age     : {safe_data.get('age', 'Not specified')}
- Patient Gender  : {safe_data.get('gender', 'Not specified')}
- Known Allergies : {safe_data.get('allergies', 'None known')}
- Comorbidities   : {safe_data.get('comorbidities', 'None')}

INSTRUCTIONS:
- Use generic drug names (not brand names)
- ICD-11 code is mandatory for primary diagnosis
- List differentials in order of likelihood
- confidence_score: 0-100, how confident you are given the information provided
- confidence_reason: one sentence explaining the score

Return ONLY a valid JSON object matching this exact schema:
{{
    "diagnosis": {{
        "primary": "",
        "icd11_code": "",
        "differential": []
    }},
    "medications": [
        {{
            "generic_name": "",
            "dosage": "",
            "frequency": "",
            "duration": "",
            "route": "oral|iv|im|topical|inhaled|other",
            "special_instructions": "",
            "timing": "",
            "benefits": [],
            "potential_side_effects": {{
                "common": [],
                "serious": [],
                "what_to_do": ""
            }},
            "precautions": [],
            "interactions": [],
            "alternatives": [
                {{
                    "name": "",
                    "composition": "same/different",
                    "price_savings": 0,
                    "reason": ""
                }}
            ],
            "max_daily": "",
            "with_food": "yes/no/optional"
        }}
    ],
    "investigations": [
        {{
            "test": "",
            "reason": "",
            "urgency": "routine|urgent|stat"
        }}
    ],
    "referral": {{
        "required": false,
        "specialty": "",
        "reason": ""
    }},
    "advice": [],
    "red_flags": [],
    "follow_up_days": 7,
    "confidence_score": 0,
    "confidence_reason": ""
}}
"""
    simpler_prompt = f"""
You are a qualified Modern Medicine physician (MBBS/MD).
The case details may be incomplete. Still produce the best possible structured prescription draft for doctor review.

CASE DETAILS:
{_json_case_data(safe_data)}

Return ONLY valid JSON with these keys:
diagnosis, medications, investigations, referral, advice, red_flags, follow_up_days, confidence_score, confidence_reason
"""

    try:
        result, provider = await call_ai_json_with_retry(
            system_prompt="You are a qualified Modern Medicine physician creating structured JSON prescriptions for doctor review.",
            user_prompt=prompt,
            simpler_user_prompt=simpler_prompt,
            temperature=0.3,
            max_output_tokens=2000,
        )
        missing = [key for key in ["diagnosis", "medications", "confidence_score"] if key not in result]
        if missing:
            raise RuntimeError(f"Incomplete prescription schema, missing: {missing}")
        return {
            "success": True,
            "prescription": result,
            "rendered_prescription": _render_structured_prescription(result, "modern"),
            "medicines": _normalize_prescription_medicines(result, "modern"),
            "mode": "modern",
            "confidence": result.get("confidence_score", 70),
            "references": [],
            "provider": provider,
        }
    except Exception as exc:
        logger.exception("Modern prescription generation failed: %s", exc)
        raise RuntimeError(f"AI modern prescription generation failed: {exc}") from exc


def generate_ayurveda_prescription_sync(case_data: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_get_ayurveda_prescription_impl(case_data))


async def generate_ayurveda_prescription(case_data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(generate_ayurveda_prescription_sync, case_data)


def generate_modern_prescription_sync(case_data: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_get_modern_prescription_impl(case_data))


async def generate_modern_prescription(case_data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(generate_modern_prescription_sync, case_data)


def generate_integrated_prescription_sync(case_data: dict[str, Any]) -> dict[str, Any]:
    from app.rag_engine import get_rag_engine

    query_text = _safe_case_field(case_data, "query_text", _safe_case_field(case_data, "symptoms", "No symptoms recorded."))
    patient_context = _safe_case_field(case_data, "patient_context", "")
    references: list[str] = []
    samhita_context = "No Samhita context available."
    try:
        passages = get_rag_engine().retrieve(query_text, top_k=3)
        if passages:
            references = [str(item.source_file) for item in passages]
            samhita_context = "\n".join(
                f"- {item.source_file}: {str(item.text).strip()[:280]}"
                for item in passages[:3]
            )
    except Exception as exc:
        logger.warning("Integrated prescription could not retrieve Samhita context: %s", exc)

    system_prompt = "You are an integrated medicine doctor. Provide both modern and Ayurveda perspectives in one safe prescription draft."
    user_prompt = (
        f"CASE DETAILS:\n{_json_case_data(case_data)}\n\n"
        f"RELEVANT SAMHITA REFERENCES:\n{samhita_context}\n\n"
        "Generate the prescription in this format:\n\n"
        "## Modern Medicine Perspective\n- Diagnosis with ICD-11 when appropriate\n- Recommended medicines and precautions\n\n"
        "## Ayurveda Perspective\n- Sanskrit / English diagnosis\n- Dosha / dhatu analysis\n- Herbs or formulations\n\n"
        "## Integrated Approach\n- How both approaches can work together\n- Potential interactions or cautions\n\n"
        "## Follow-up\n- Review plan and warning signs"
    )
    try:
        prescription, provider = chat_with_fallback(system_prompt, user_prompt, temperature=0.25, max_output_tokens=1800)
        return {
            "success": True,
            "prescription": prescription,
            "mode": "integrated",
            "provider": provider.value,
            "references": references,
        }
    except Exception as exc:
        logger.exception("Integrated prescription generation failed: %s", exc)
        simpler_prompt = (
            f"CASE DETAILS:\n{_json_case_data(case_data)}\n\n"
            "Provide a brief integrated doctor-review note with one modern perspective, one Ayurveda perspective, and one follow-up step."
        )
        prescription, provider = chat_with_fallback(system_prompt, simpler_prompt, temperature=0.1, max_output_tokens=1000)
        return {
            "success": True,
            "prescription": prescription,
            "mode": "integrated",
            "provider": provider.value,
            "references": references,
            "warning": str(exc),
        }


async def generate_integrated_prescription(case_data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(generate_integrated_prescription_sync, case_data)


def generate_generic_prescription_sync(case_data: dict[str, Any], mode: str) -> dict[str, Any]:
    return _call_specialty_prescription(case_data, mode)


async def generate_generic_prescription(case_data: dict[str, Any], mode: str) -> dict[str, Any]:
    return await asyncio.to_thread(generate_generic_prescription_sync, case_data, mode)


def generate_role_based_prescription_sync(case_data: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized = str(mode or "general").strip().lower()
    if normalized == "ayurveda":
        return generate_ayurveda_prescription_sync(case_data)
    if normalized == "modern":
        return generate_modern_prescription_sync(case_data)
    if normalized == "integrated":
        return generate_integrated_prescription_sync(case_data)
    return generate_generic_prescription_sync(case_data, normalized)


async def generate_role_based_prescription(case_data: dict[str, Any], mode: str) -> dict[str, Any]:
    return await asyncio.to_thread(generate_role_based_prescription_sync, case_data, mode)


async def get_ayurveda_prescription(case_data: dict[str, Any]) -> dict[str, Any]:
    return await _get_ayurveda_prescription_impl(case_data)


async def get_modern_prescription(case_data: dict[str, Any]) -> dict[str, Any]:
    return await _get_modern_prescription_impl(case_data)


def get_ai_response(prompt: str | dict[str, Any], mode: str = "samhita", context: dict | None = None) -> dict[str, Any]:
    """Return a mode-aware AI response for the analyzer and doctor tools."""
    if isinstance(prompt, dict):
        doctor_type = (mode or "ayurveda").strip().lower()
        if doctor_type in {"ayurveda", "samhita"}:
            return asyncio.run(get_ayurveda_prescription(prompt))
        if doctor_type == "modern":
            return asyncio.run(get_modern_prescription(prompt))
        return {"success": False, "error": f"Unknown doctor_type: {doctor_type}"}

    context = context or {}
    context_block = json.dumps(context, ensure_ascii=True, indent=2) if context else "{}"
    mode_prompts = {
        "samhita": (
            "You are an Ayurveda expert answering from classical texts like Charak Samhita, "
            "Sushruta Samhita, and Ashtanga Hridaya. Provide: "
            "1. classical reference when available, 2. Ayurvedic interpretation, 3. practical next step."
        ),
        "modern": (
            "You are a modern medicine clinician. Answer using evidence-based medicine, "
            "clinical reasoning, and safe contemporary guidance."
        ),
        "integrated": (
            "You are an integrated medicine expert. Provide both modern and Ayurvedic perspectives, "
            "then explain how they can work together safely."
        ),
        "general": (
            "You are a helpful healthcare AI assistant. Be conversational, helpful, and clinically safe."
        ),
    }
    normalized_mode = (mode or "samhita").strip().lower()
    system_prompt = mode_prompts.get(normalized_mode, mode_prompts["samhita"])
    user_prompt = (
        f"Question:\n{prompt.strip()}\n\n"
        f"Structured context:\n{context_block}\n\n"
        "Keep the answer practical and safe, and avoid pretending to have certainty where details are missing."
    )
    try:
        answer, provider = chat_with_fallback(system_prompt, user_prompt, temperature=0.3)
        return {"answer": answer, "mode": normalized_mode, "provider": provider.value}
    except Exception as exc:
        logger.exception("Mode-aware AI response failed: %s", exc)
        simpler_prompt = (
            f"Question:\n{str(prompt).strip()[:1200]}\n\n"
            "Give a brief, safe clinical answer with likely considerations, immediate advice, and doctor-review caution."
        )
        answer, provider = chat_with_fallback(system_prompt, simpler_prompt, temperature=0.1)
        return {"answer": answer, "mode": normalized_mode, "provider": provider.value, "warning": str(exc)}
