import json
import logging

try:
    from services.ai_provider import call_ai_json_with_retry
except Exception as exc:
    _ai_provider_import_error = str(exc)
    async def call_ai_json_with_retry(*args, **kwargs):
        raise RuntimeError(f"AI provider unavailable: {_ai_provider_import_error}")


logger = logging.getLogger(__name__)


def _safe_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


async def generate_diet_plan(patient_data: dict) -> dict:
    system_prompt = "You are a senior Ayurvedic physician. Return only valid JSON."
    user_prompt = (
        "Create a structured Ayurvedic diet plan for this patient.\n"
        "Return JSON only with practical fields such as diagnosis_summary, dosha_assessment, "
        "meal_plan, foods_to_favor, foods_to_avoid, lifestyle_tips, and precautions.\n\n"
        f"Patient data:\n{json.dumps(patient_data, indent=2, ensure_ascii=True)}"
    )
    simpler_prompt = (
        "Create a short structured Ayurvedic diet plan from the limited patient context below.\n"
        "Return JSON only with diagnosis_summary, meal_plan, foods_to_favor, foods_to_avoid, lifestyle_tips, and precautions.\n\n"
        f"Patient data:\n{json.dumps(patient_data, ensure_ascii=True)}"
    )
    payload, provider = await call_ai_json_with_retry(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        simpler_user_prompt=simpler_prompt,
        temperature=0.3,
        max_output_tokens=4096,
    )
    logger.info("Diet plan generated using %s", provider)
    return payload


def generate_whatsapp_message(patient_name: str, diet_plan: dict) -> str:
    greeting_name = (patient_name or "Patient").strip()
    summary = diet_plan.get("diagnosis_summary") or diet_plan.get("summary") or "Your Ayurvedic diet plan is ready."

    foods_to_favor = diet_plan.get("foods_to_favor") or []
    foods_to_avoid = diet_plan.get("foods_to_avoid") or []
    lifestyle_tips = diet_plan.get("lifestyle_tips") or []

    def _as_lines(values: list) -> str:
        if not values:
            return "Not specified"
        return ", ".join(str(value).strip() for value in values if str(value).strip())

    return (
        f"Namaste {greeting_name},\n\n"
        f"{summary}\n\n"
        f"Foods to favor: {_as_lines(foods_to_favor)}\n"
        f"Foods to avoid: {_as_lines(foods_to_avoid)}\n"
        f"Lifestyle tips: {_as_lines(lifestyle_tips)}\n\n"
        "Please follow the plan as advised by your doctor."
    )
