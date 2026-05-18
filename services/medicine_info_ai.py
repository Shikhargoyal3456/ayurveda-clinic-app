from __future__ import annotations

import logging
from typing import Any

from services.ai_provider import call_ai_json_with_retry
from services.cache_service import cache_result


logger = logging.getLogger(__name__)


def calculate_confidence(result: dict[str, Any]) -> int:
    confidence = 70
    if len(result.get("benefits", []) or []) >= 3:
        confidence += 10
    if len((result.get("side_effects", {}) or {}).get("common", []) or []) >= 2:
        confidence += 10
    if (result.get("dosage", {}) or {}).get("standard"):
        confidence += 5
    if result.get("precautions"):
        confidence += 5
    return min(confidence, 98)


def _clean_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _clean_alternatives(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    cleaned: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        why_recommended = str(value.get("why_recommended") or "").strip()
        estimated_savings = str(value.get("estimated_savings") or "").strip()
        if not (name and why_recommended and estimated_savings):
            continue
        cleaned.append(
            {
                "name": name,
                "why_recommended": why_recommended,
                "estimated_savings": estimated_savings,
            }
        )
    return cleaned


def _validate_non_empty(result: dict[str, Any], medicine_name: str) -> dict[str, Any]:
    side_effects = result.get("side_effects")
    dosage = result.get("dosage")
    if not isinstance(side_effects, dict):
        raise ValueError(f"AI response missing side_effects for {medicine_name}")
    if not isinstance(dosage, dict):
        raise ValueError(f"AI response missing dosage for {medicine_name}")

    validated = {
        "medicine_name": str(result.get("medicine_name") or medicine_name).strip(),
        "benefits": _clean_list(result.get("benefits")),
        "side_effects": {
            "common": _clean_list(side_effects.get("common")),
            "serious": _clean_list(side_effects.get("serious")),
            "management": str(side_effects.get("management") or "").strip(),
        },
        "alternatives": _clean_alternatives(result.get("alternatives")),
        "dosage": {
            "standard": str(dosage.get("standard") or "").strip(),
            "max_daily": str(dosage.get("max_daily") or "").strip(),
            "timing": str(dosage.get("timing") or "").strip(),
            "food_instruction": str(dosage.get("food_instruction") or "").strip(),
        },
        "precautions": _clean_list(result.get("precautions")),
        "interactions": _clean_list(result.get("interactions")),
        "what_to_do_if_missed": str(result.get("what_to_do_if_missed") or "").strip(),
        "when_to_consult_doctor": str(result.get("when_to_consult_doctor") or "").strip(),
    }

    required_checks = {
        "benefits": bool(validated["benefits"]),
        "side_effects.common": bool(validated["side_effects"]["common"]),
        "side_effects.serious": bool(validated["side_effects"]["serious"]),
        "side_effects.management": bool(validated["side_effects"]["management"]),
        "alternatives": bool(validated["alternatives"]),
        "dosage.standard": bool(validated["dosage"]["standard"]),
        "dosage.max_daily": bool(validated["dosage"]["max_daily"]),
        "dosage.timing": bool(validated["dosage"]["timing"]),
        "dosage.food_instruction": bool(validated["dosage"]["food_instruction"]),
        "precautions": bool(validated["precautions"]),
        "interactions": bool(validated["interactions"]),
        "what_to_do_if_missed": bool(validated["what_to_do_if_missed"]),
        "when_to_consult_doctor": bool(validated["when_to_consult_doctor"]),
    }
    missing = [key for key, present in required_checks.items() if not present]
    if missing:
        raise ValueError(f"AI response missing required fields for {medicine_name}: {', '.join(missing)}")

    validated["ai_confidence_percent"] = calculate_confidence(validated)
    validated["source"] = "ai"
    return validated


@cache_result(ttl=3600)
async def get_medicine_info_pure_ai(medicine_name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_name = str(medicine_name or "").strip()
    if not normalized_name:
        raise ValueError("medicine_name is required")

    context = context or {}
    diagnosis_text = str(context.get("diagnosis") or "Not specified").strip() or "Not specified"
    symptoms_text = str(context.get("symptoms") or "Not specified").strip() or "Not specified"
    age_text = str(context.get("age") or "Not specified").strip() or "Not specified"

    prompt = f"""
You are a clinical pharmacologist. Provide COMPLETE information about {normalized_name}.

Context:
- Diagnosis: {diagnosis_text}
- Symptoms: {symptoms_text}
- Patient age: {age_text}

Return ONLY valid JSON. DO NOT include any explanatory text outside JSON.

{{
    "medicine_name": "{normalized_name}",
    "benefits": [
        "AI-generated benefit statement 1",
        "AI-generated benefit statement 2",
        "AI-generated benefit statement 3"
    ],
    "side_effects": {{
        "common": ["AI-generated common effect 1", "AI-generated common effect 2"],
        "serious": ["AI-generated serious effect 1", "AI-generated serious effect 2"],
        "management": "AI-generated advice on managing side effects"
    }},
    "alternatives": [
        {{
            "name": "Alternative medicine name",
            "why_recommended": "AI-generated reason",
            "estimated_savings": "AI-generated estimated savings"
        }}
    ],
    "dosage": {{
        "standard": "AI-generated standard dosage",
        "max_daily": "AI-generated maximum daily dose",
        "timing": "AI-generated timing instruction",
        "food_instruction": "AI-generated food interaction instruction"
    }},
    "precautions": [
        "AI-generated precaution 1",
        "AI-generated precaution 2"
    ],
    "interactions": [
        "AI-generated drug interaction 1",
        "AI-generated drug interaction 2"
    ],
    "what_to_do_if_missed": "AI-generated instruction for missed dose",
    "when_to_consult_doctor": "AI-generated warning signs"
}}

IMPORTANT:
- Every field MUST contain unique, specific information about {normalized_name}.
- Do not use placeholders.
- Do not omit fields.
- Do not write markdown.
"""
    simpler_prompt = f"""
Medicine: {normalized_name}
Diagnosis: {diagnosis_text}
Symptoms: {symptoms_text}
Age: {age_text}

Return only JSON with fields:
medicine_name, benefits, side_effects, alternatives, dosage, precautions, interactions, what_to_do_if_missed, when_to_consult_doctor
"""

    parsed, provider = await call_ai_json_with_retry(
        system_prompt="You are a clinical pharmacologist returning strict JSON only.",
        user_prompt=prompt,
        simpler_user_prompt=simpler_prompt,
        temperature=0.2,
        max_output_tokens=2200,
    )
    validated = _validate_non_empty(parsed, normalized_name)
    validated["provider"] = provider
    logger.info("Pure AI medicine info generated for %s via %s", normalized_name, provider)
    return validated


@cache_result(ttl=3600)
async def get_complete_medicine_info(
    medicine_name: str,
    diagnosis: str = "",
    symptoms: str = "",
) -> dict[str, Any]:
    return await get_medicine_info_pure_ai(
        medicine_name,
        {
            "diagnosis": diagnosis,
            "symptoms": symptoms,
        },
    )


async def get_prescription_with_details(prescription_data: dict[str, Any]) -> dict[str, Any]:
    medicines = prescription_data.get("medicines", [])
    if not isinstance(medicines, list):
        raise ValueError("medicines must be a list")

    context = {
        "diagnosis": str(prescription_data.get("diagnosis") or "").strip(),
        "symptoms": str(prescription_data.get("symptoms") or "").strip(),
        "age": prescription_data.get("age"),
    }

    enhanced_medicines: list[dict[str, Any]] = []
    for medicine in medicines:
        if not isinstance(medicine, dict):
            raise ValueError("Each medicine must be an object")
        medicine_name = str(medicine.get("name") or medicine.get("generic_name") or "").strip()
        if not medicine_name:
            raise ValueError("Each medicine must include a name or generic_name")
        detailed_info = await get_medicine_info_pure_ai(medicine_name, context)
        enhanced_medicines.append({**medicine, "detailed_info": detailed_info})

    return {
        **prescription_data,
        "medicines": enhanced_medicines,
        "ai_generated": True,
        "source": "ai",
    }
