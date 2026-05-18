from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.ai_provider import GEMINI_API_KEY, chat_with_fallback, chat_with_gemini, parse_json_response
from services.voice_ai import transcribe_audio


logger = logging.getLogger(__name__)


def _safe_text(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


def _normalize_age_text(value: Any) -> str:
    text = _safe_text(value, 40)
    if not text:
        return ""
    match = re.search(r"\b(\d{1,3})\b", text)
    return match.group(1) if match else text


def _clean_list(values: Any, limit: int = 8) -> list[str]:
    if isinstance(values, list):
        return [_safe_text(item, 160) for item in values if _safe_text(item, 160)][:limit]
    if isinstance(values, str):
        items = re.split(r"[,;\n]+", values)
        return [_safe_text(item, 160) for item in items if _safe_text(item, 160)][:limit]
    return []


def _normalize_prescription_items(values: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(values, list):
        for entry in values:
            if isinstance(entry, dict):
                name = _safe_text(entry.get("name"), 120)
                if not name:
                    continue
                items.append(
                    {
                        "name": name,
                        "dosage": _safe_text(entry.get("dosage"), 120) or "As directed",
                        "frequency": _safe_text(entry.get("frequency"), 120) or _safe_text(entry.get("instructions"), 160) or "As directed",
                        "duration": _safe_text(entry.get("duration"), 120) or "As directed",
                    }
                )
            else:
                text = _safe_text(entry, 120)
                if text:
                    items.append({"name": text, "dosage": "As directed", "frequency": "As directed", "duration": "As directed"})
    elif isinstance(values, str):
        for line in re.split(r"[\n;]+", values):
            text = _safe_text(line, 120)
            if text:
                items.append({"name": text, "dosage": "As directed", "frequency": "As directed", "duration": "As directed"})
    return items[:6]


class AmbientEMRService:
    """Session-scoped ambient conversation to EMR extraction."""

    def __init__(self, patient_context: dict[str, Any] | None = None):
        self.patient_context = patient_context or {}
        self.reset_session()

    def reset_session(self) -> None:
        self.conversation_history: list[dict[str, Any]] = []
        self.extracted_data: dict[str, Any] = {
            "patient_name": _safe_text(self.patient_context.get("name"), 160),
            "age": _normalize_age_text(self.patient_context.get("age")),
            "gender": _safe_text(self.patient_context.get("gender"), 20),
            "chief_complaint": "",
            "history_present_illness": "",
            "past_medical_history": "",
            "medications": [],
            "allergies": [],
            "examination_findings": "",
            "diagnosis": "",
            "treatment_plan": "",
            "prescription": [],
        }

    async def process_conversation_segment(
        self,
        audio_file: Any | None = None,
        *,
        transcript_text: str = "",
        speaker: str = "auto",
    ) -> dict[str, Any]:
        transcript = _safe_text(transcript_text, 4000)
        if not transcript and audio_file is not None:
            transcript = await self.transcribe(audio_file)

        resolved_speaker = self._resolve_speaker(speaker, transcript)
        if transcript:
            self.conversation_history.append(
                {
                    "speaker": resolved_speaker,
                    "text": transcript,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            await self.extract_emr_from_conversation()

        return {
            "transcript": transcript,
            "speaker": resolved_speaker,
            "conversation_history": self.conversation_history,
            "extracted_data": self.extracted_data,
        }

    def _resolve_speaker(self, speaker: str, transcript: str) -> str:
        normalized = _safe_text(speaker, 20).lower()
        if normalized in {"doctor", "patient"}:
            return normalized
        if transcript.endswith("?"):
            return "doctor"
        if self.conversation_history:
            last = str(self.conversation_history[-1].get("speaker") or "patient")
            return "doctor" if last == "patient" else "patient"
        return "patient"

    async def extract_emr_from_conversation(self) -> dict[str, Any]:
        ai_payload = self._extract_with_ai()
        if ai_payload:
            self._merge_extracted_data(ai_payload)
        else:
            self._merge_extracted_data(self._extract_with_rules())
        self._backfill_defaults()
        return self.extracted_data

    def _conversation_text(self) -> str:
        return "\n".join(
            f"{entry.get('speaker', 'patient').title()}: {entry.get('text', '')}"
            for entry in self.conversation_history
            if _safe_text(entry.get("text"))
        )

    def _extract_with_ai(self) -> dict[str, Any] | None:
        conversation_text = self._conversation_text()
        if not conversation_text:
            return None

        system_prompt = (
            "You are an ambient clinical scribe for Kash AI. "
            "Extract structured EMR fields from the conversation and return only valid JSON. "
            "Keep strings concise and clinically useful. Use empty strings or empty arrays when unknown."
        )
        user_prompt = json.dumps(
            {
                "patient_context": self.patient_context,
                "conversation": self.conversation_history,
                "required_schema": {
                    "patient_name": "string",
                    "age": "string",
                    "gender": "string",
                    "chief_complaint": "string",
                    "history_present_illness": "string",
                    "past_medical_history": "string",
                    "medications": ["string"],
                    "allergies": ["string"],
                    "examination_findings": "string",
                    "diagnosis": "string",
                    "treatment_plan": "string",
                    "prescription": [{"name": "string", "dosage": "string", "frequency": "string", "duration": "string"}],
                },
            },
            ensure_ascii=True,
        )
        try:
            if GEMINI_API_KEY:
                raw = chat_with_gemini(system_prompt, user_prompt, temperature=0.1, response_mime_type="application/json", max_output_tokens=2048)
            else:
                raw, _ = chat_with_fallback(system_prompt, user_prompt, temperature=0.1, response_mime_type="application/json", max_output_tokens=2048)
            parsed = parse_json_response(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.info("Ambient EMR AI extraction fell back to regex rules: %s", exc)
            return None

    def _extract_with_rules(self) -> dict[str, Any]:
        full_text = self._conversation_text()
        patient_lines = " ".join(entry["text"] for entry in self.conversation_history if entry.get("speaker") == "patient")
        doctor_lines = " ".join(entry["text"] for entry in self.conversation_history if entry.get("speaker") == "doctor")

        extracted: dict[str, Any] = {
            "patient_name": "",
            "age": "",
            "gender": "",
            "chief_complaint": "",
            "history_present_illness": "",
            "past_medical_history": "",
            "medications": [],
            "allergies": [],
            "examination_findings": "",
            "diagnosis": "",
            "treatment_plan": "",
            "prescription": [],
        }

        name_match = re.search(r"(?:my name is|i am|this is|patient name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", full_text, re.IGNORECASE)
        if name_match:
            extracted["patient_name"] = _safe_text(name_match.group(1), 160)

        age_match = re.search(r"\b(\d{1,3})\s*(?:years old|year old|yrs old|yrs|years)\b", full_text, re.IGNORECASE) or re.search(r"\bage\s+(\d{1,3})\b", full_text, re.IGNORECASE)
        if age_match:
            extracted["age"] = _safe_text(age_match.group(1), 10)

        gender_match = re.search(r"\b(male|female|man|woman|boy|girl)\b", full_text, re.IGNORECASE)
        if gender_match:
            value = gender_match.group(1).lower()
            extracted["gender"] = "Male" if value in {"male", "man", "boy"} else "Female"

        patient_sentences = [part.strip() for part in re.split(r"[.?!]\s*", patient_lines) if part.strip()]
        if patient_sentences:
            extracted["chief_complaint"] = patient_sentences[0][:220]
            extracted["history_present_illness"] = " ".join(patient_sentences[:3])[:500]

        history_matches = re.findall(
            r"(?:history of|past medical history|diagnosed with|suffers from|have had)\s+([^.;\n]+)",
            full_text,
            re.IGNORECASE,
        )
        if history_matches:
            extracted["past_medical_history"] = "; ".join(_safe_text(item, 160) for item in history_matches[:4])

        meds = re.findall(r"(?:taking|on|prescribed)\s+([A-Za-z][A-Za-z0-9+\- ]{1,40})", full_text, re.IGNORECASE)
        extracted["medications"] = sorted({item.strip().rstrip(",.") for item in meds if item.strip()})[:6]

        allergy_matches = re.findall(r"(?:allergic to|allergy to|allergies include)\s+([^.;\n]+)", full_text, re.IGNORECASE)
        extracted["allergies"] = [item.strip() for item in allergy_matches[:4] if item.strip()]

        exam_matches = re.findall(r"(?:on examination|exam shows|findings include)\s+([^.;\n]+)", full_text, re.IGNORECASE)
        if exam_matches:
            extracted["examination_findings"] = "; ".join(_safe_text(item, 180) for item in exam_matches[:3])

        diagnosis_match = re.search(r"(?:diagnosis is|i think you have|you have|diagnosed with)\s+([^.;\n]+)", doctor_lines, re.IGNORECASE)
        if diagnosis_match:
            extracted["diagnosis"] = _safe_text(diagnosis_match.group(1), 180)

        treatment_match = re.search(r"(?:treatment plan is|plan is|advised|recommend)\s+([^.;\n]+)", doctor_lines, re.IGNORECASE)
        if treatment_match:
            extracted["treatment_plan"] = _safe_text(treatment_match.group(1), 220)

        prescription_items = []
        for med in extracted["medications"][:4]:
            prescription_items.append({"name": med, "dosage": "As directed", "frequency": "As directed", "duration": "As directed"})
        extracted["prescription"] = prescription_items
        return extracted

    def _merge_extracted_data(self, payload: dict[str, Any]) -> None:
        for key in self.extracted_data.keys():
            if key not in payload:
                continue
            if key in {"medications", "allergies"}:
                values = _clean_list(payload.get(key))
                if values:
                    self.extracted_data[key] = values
            elif key == "prescription":
                items = _normalize_prescription_items(payload.get(key))
                if items:
                    self.extracted_data[key] = items
            else:
                value = _normalize_age_text(payload.get(key)) if key == "age" else _safe_text(payload.get(key), 600)
                if value:
                    self.extracted_data[key] = value

    def _backfill_defaults(self) -> None:
        if not self.extracted_data["patient_name"]:
            self.extracted_data["patient_name"] = _safe_text(self.patient_context.get("name"), 160)
        if not self.extracted_data["age"] and self.patient_context.get("age") not in {None, ""}:
            self.extracted_data["age"] = _normalize_age_text(self.patient_context.get("age"))
        if not self.extracted_data["gender"]:
            self.extracted_data["gender"] = _safe_text(self.patient_context.get("gender"), 20)
        if not self.extracted_data["chief_complaint"] and self.conversation_history:
            self.extracted_data["chief_complaint"] = _safe_text(self.conversation_history[0].get("text"), 220)

    async def transcribe(self, audio_file: Any) -> str:
        suffix = getattr(audio_file, "filename", "") or ".webm"
        extension = Path(suffix).suffix.lower() or ".webm"
        temp_path = ""
        try:
            fd, temp_path = tempfile.mkstemp(suffix=extension)
            with os.fdopen(fd, "wb") as handle:
                contents = audio_file.read()
                handle.write(contents if isinstance(contents, (bytes, bytearray)) else b"")
            return _safe_text(transcribe_audio(temp_path, "auto"), 4000)
        except Exception as exc:
            logger.warning("Ambient EMR transcription failed: %s", exc)
            return ""
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def get_emr_json(self) -> dict[str, Any]:
        return {
            **self.extracted_data,
            "conversation_history": list(self.conversation_history),
        }
