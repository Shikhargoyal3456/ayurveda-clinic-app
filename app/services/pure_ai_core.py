from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from services.ai_provider import call_ai_json_with_retry
from services.cache_service import intelligent_cache


MEDICAL_DISCLAIMER = """
⚠️ AI-GENERATED CONTENT - NOT A FINAL DIAGNOSIS
- This is an AI-assisted suggestion
- Always consult a qualified doctor
- Do not make medical decisions based solely on AI
- For emergencies, seek immediate medical attention
""".strip()


def add_disclaimer(response: dict[str, Any]) -> dict[str, Any]:
    response["disclaimer"] = MEDICAL_DISCLAIMER
    response["ai_generated"] = True
    response["not_medical_advice"] = True
    return response


class PureAICore:
    """100% AI-powered healthcare intelligence with no static clinical payloads."""

    def __init__(self) -> None:
        self.cache_ttl = 3600

    def _decorate_response(self, payload: dict[str, Any], default_confidence: int = 85) -> dict[str, Any]:
        confidence = int(payload.get("confidence") or payload.get("confidence_score") or default_confidence)
        payload["confidence"] = max(1, min(99, confidence))
        payload.setdefault(
            "confidence_factors",
            {
                "data_completeness": "moderate",
                "clinical_match": "moderate",
                "evidence_strength": "moderate",
            },
        )
        payload.setdefault("requires_doctor_review", False)
        return add_disclaimer(payload)

    async def get_medicine_info(self, medicine_name: str, patient_context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = patient_context or {}

        async def _generate() -> dict[str, Any]:
            prompt = f"""
Generate COMPLETE medicine information for {medicine_name}.

Patient Context:
- Age: {context.get('age', 'Not specified')}
- Condition: {context.get('condition', 'Not specified')}
- Other medicines: {context.get('current_medicines', 'None')}
- Allergies: {context.get('allergies', 'None')}

Return ONLY valid JSON:
{{
  "medicine_name": "{medicine_name}",
  "benefits": ["benefit 1", "benefit 2", "benefit 3"],
  "side_effects": {{
    "common": ["effect 1", "effect 2"],
    "serious": ["effect 1", "effect 2"]
  }},
  "dosage": {{
    "standard": "context-aware dosage guidance",
    "max_daily": "max daily guidance",
    "pediatric": "pediatric note if relevant"
  }},
  "alternatives": [
    {{"name": "Alternative 1", "savings_percent": 20, "reason": "why it may fit"}}
  ],
  "interactions": ["interaction 1", "interaction 2"],
  "confidence": 85,
  "confidence_factors": {{
    "data_completeness": "high|moderate|low",
    "clinical_match": "high|moderate|low",
    "evidence_strength": "high|moderate|low"
  }},
  "requires_doctor_review": false
}}
""".strip()
            result, _provider = await call_ai_json_with_retry(
                system_prompt="You generate careful structured medicine information for doctor review. Return only JSON.",
                user_prompt=prompt,
                simpler_user_prompt=f"Return JSON medicine information for {medicine_name} using the provided patient context.",
                temperature=0.25,
                max_output_tokens=1600,
            )
            return self._decorate_response(result)

        query = f"medicine-info:{medicine_name}"
        return await intelligent_cache.get_or_generate(query, context, _generate, ttl=3600)

    async def generate_personalized_prescription(self, patient_data: dict[str, Any], doctor_notes: str | None = None) -> dict[str, Any]:
        context = {"patient_data": patient_data, "doctor_notes": doctor_notes or ""}

        async def _generate() -> dict[str, Any]:
            prompt = f"""
Generate a personalized medical prescription.

PATIENT:
- Age: {patient_data.get('age', 'Not specified')}
- Gender: {patient_data.get('gender', 'Not specified')}
- Weight: {patient_data.get('weight', 'Not specified')}
- Known allergies: {patient_data.get('allergies', 'None')}
- Current conditions: {patient_data.get('conditions', 'None')}
- Current medicines: {patient_data.get('current_medicines', 'None')}

SYMPTOMS OR DIAGNOSIS:
{patient_data.get('diagnosis', 'Not specified')}

DOCTOR NOTES:
{doctor_notes or 'None'}

Return ONLY valid JSON:
{{
  "diagnosis": "AI-generated working diagnosis",
  "medicines": [
    {{
      "name": "Medicine name",
      "dosage": "AI-calculated dosage",
      "frequency": "AI frequency",
      "duration": "AI duration",
      "notes": "AI special instructions"
    }}
  ],
  "lifestyle_advice": ["advice 1", "advice 2"],
  "follow_up_days": 0,
  "confidence": 85,
  "confidence_factors": {{
    "data_completeness": "high|moderate|low",
    "clinical_match": "high|moderate|low",
    "evidence_strength": "high|moderate|low"
  }},
  "requires_doctor_review": false
}}
""".strip()
            result, _provider = await call_ai_json_with_retry(
                system_prompt="You generate cautious, structured prescription drafts for doctor review. Return only JSON.",
                user_prompt=prompt,
                simpler_user_prompt="Return JSON with diagnosis, medicines, lifestyle_advice, follow_up_days, confidence, and confidence_factors.",
                temperature=0.25,
                max_output_tokens=1700,
            )
            return self._decorate_response(result)

        return await intelligent_cache.get_or_generate("prescription", context, _generate, ttl=7200)

    async def schedule_followup(self, patient_data: dict[str, Any], treatment_response: str | None = None) -> dict[str, Any]:
        context = {"patient_data": patient_data, "treatment_response": treatment_response or ""}

        async def _generate() -> dict[str, Any]:
            prompt = f"""
Determine optimal follow-up scheduling for this patient.

PATIENT:
- Condition: {patient_data.get('condition', 'Not specified')}
- Severity: {patient_data.get('severity', 'Medium')}
- Treatment phase: {patient_data.get('phase', 'Initial')}
- Age: {patient_data.get('age', 'Not specified')}
- Preferred days: {patient_data.get('preferred_days', 'Any')}
- Preferred time: {patient_data.get('preferred_time', 'Any')}
- Urgency requested: {patient_data.get('requested_urgency', 'Normal')}

TREATMENT RESPONSE:
{treatment_response or 'Not yet assessed'}

Today is {date.today().isoformat()}.

Return ONLY valid JSON:
{{
  "recommended_followup_days": 0,
  "recommended_date": "YYYY-MM-DD",
  "urgency_level": "Low|Medium|High",
  "reasoning": "clinical reasoning",
  "flexible_options": [
    {{"days": 0, "rationale": "why this variation may help"}}
  ],
  "confidence": 85,
  "confidence_factors": {{
    "data_completeness": "high|moderate|low",
    "clinical_match": "high|moderate|low",
    "evidence_strength": "high|moderate|low"
  }},
  "requires_doctor_review": false
}}
""".strip()
            result, _provider = await call_ai_json_with_retry(
                system_prompt="You determine careful follow-up timing recommendations for doctor review. Return only JSON.",
                user_prompt=prompt,
                simpler_user_prompt="Return JSON with recommended_followup_days, recommended_date, urgency_level, reasoning, flexible_options, confidence, and confidence_factors.",
                temperature=0.2,
                max_output_tokens=1400,
            )
            if not result.get("recommended_date"):
                days = int(result.get("recommended_followup_days") or 7)
                result["recommended_date"] = (date.today() + timedelta(days=days)).isoformat()
            return self._decorate_response(result)

        return await intelligent_cache.get_or_generate("followup", context, _generate, ttl=1800)

    async def reschedule_appointment_ai(
        self,
        current_appointment: dict[str, Any],
        patient_message: str,
        doctor_schedule: list[dict[str, Any]],
    ) -> dict[str, Any]:
        context = {
            "current_appointment": current_appointment,
            "patient_message": patient_message,
            "doctor_schedule": doctor_schedule,
        }

        async def _generate() -> dict[str, Any]:
            prompt = f"""
Parse this patient reschedule request and find an optimal new time.

CURRENT APPOINTMENT:
- Date: {current_appointment.get('date')}
- Time: {current_appointment.get('time')}
- Doctor: {current_appointment.get('doctor_name')}

PATIENT MESSAGE:
{patient_message}

DOCTOR AVAILABILITY NEXT 14 DAYS:
{doctor_schedule}

Return ONLY valid JSON:
{{
  "understood_request": "What AI understood",
  "suggested_new_date": "YYYY-MM-DD",
  "suggested_new_time": "HH:MM",
  "alternative_options": [
    {{"date": "YYYY-MM-DD", "time": "HH:MM", "available": true}}
  ],
  "requires_doctor_approval": false,
  "confidence": 85,
  "confidence_factors": {{
    "data_completeness": "high|moderate|low",
    "clinical_match": "high|moderate|low",
    "evidence_strength": "high|moderate|low"
  }}
}}
""".strip()
            result, _provider = await call_ai_json_with_retry(
                system_prompt="You interpret natural-language appointment reschedule requests and return only JSON.",
                user_prompt=prompt,
                simpler_user_prompt="Return JSON with understood_request, suggested_new_date, suggested_new_time, alternative_options, requires_doctor_approval, and confidence.",
                temperature=0.2,
                max_output_tokens=1300,
            )
            return self._decorate_response(result)

        return await intelligent_cache.get_or_generate("reschedule", context, _generate, ttl=1800)

    def schedule_followup_sync(self, patient_data: dict[str, Any], treatment_response: str | None = None) -> dict[str, Any]:
        return asyncio.run(self.schedule_followup(patient_data, treatment_response))

    def get_medicine_info_sync(self, medicine_name: str, patient_context: dict[str, Any] | None = None) -> dict[str, Any]:
        return asyncio.run(self.get_medicine_info(medicine_name, patient_context))


pure_ai = PureAICore()
