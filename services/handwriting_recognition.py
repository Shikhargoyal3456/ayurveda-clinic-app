from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

from app.database import SessionLocal
from models.medicine import MasterMedicine
from services.ai_prescription_analyzer import AIPrescriptionAnalyzer
from services.ai_provider import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    ai_budget_fallback_message,
    call_gemini,
    is_ai_budget_error,
    parse_json_response,
)
from services.image_preprocessor import ImagePreprocessor

try:  # pragma: no cover
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


logger = logging.getLogger(__name__)


FREQUENCY_MAP = {
    "od": "Once daily",
    "qd": "Once daily",
    "bd": "Twice daily",
    "bid": "Twice daily",
    "tds": "Three times daily",
    "tid": "Three times daily",
    "qid": "Four times daily",
    "hs": "At bedtime",
    "sos": "As needed",
    "prn": "As needed",
    "stat": "Immediately",
}
INSTRUCTION_PATTERNS = [
    "before food",
    "after food",
    "with water",
    "with milk",
    "with honey",
    "empty stomach",
    "at bedtime",
    "after breakfast",
    "after lunch",
    "after dinner",
]


class HandwritingRecognitionService:
    """AI-powered handwriting recognition for hard-to-read prescriptions."""

    def __init__(self) -> None:
        self._medicine_analyzer = AIPrescriptionAnalyzer()
        self._image_processor = ImagePreprocessor()
        self._local_medicine_db = self._load_local_medicine_db()

    async def decode_prescription(self, image_data: str, mime_type: str = "image/jpeg") -> dict[str, Any]:
        enhancement = self._image_processor.enhance_data_url(image_data, mime_type)
        prompt = self._build_decoder_prompt()

        try:
            response = await self._call_gemini_with_image(prompt, enhancement["image_data"], enhancement["mime_type"])
            payload = self._normalize_payload(parse_json_response(response), enhancement)
        except Exception as exc:
            logger.warning("Handwriting decode fell back: %s", exc)
            if is_ai_budget_error(exc):
                return self._fallback_payload(
                    warning=ai_budget_fallback_message(),
                    unreadable_parts=["AI handwriting recognition is temporarily unavailable due to usage limits."],
                    enhancement=enhancement,
                )
            return self._fallback_payload(
                warning="Could not confidently decode the prescription image.",
                unreadable_parts=["The handwriting or image was unclear. Please verify with your doctor or pharmacist."],
                enhancement=enhancement,
            )

        payload["enhanced_preview"] = enhancement["image_data"]
        payload["image_quality_breakdown"] = enhancement["image_quality_breakdown"]
        payload["applied_preprocessing"] = enhancement["applied_steps"]
        payload["raw_decoded_text"] = payload.get("raw_decoded_text") or self._compose_raw_text(payload["medicines"])
        payload["confidence_overall"] = self._calculate_overall_confidence(payload)
        payload["requires_verification"] = payload["confidence_overall"] < 70 or bool(payload["unreadable_parts"])
        return payload

    async def enhance_with_medicine_info(self, medicines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enhanced: list[dict[str, Any]] = []
        for med in medicines:
            item = dict(med)
            medicine_name = str(item.get("medicine_name") or "").strip()
            if not medicine_name:
                enhanced.append(item)
                continue

            info = self._fallback_medicine_info(medicine_name)
            item["medicine_info"] = {
                "uses": self._string_list(info.get("uses")),
                "side_effects": self._string_list(info.get("side_effects")),
                "prescription_required": bool(info.get("prescription_required", False)),
                "category": str(info.get("category") or ""),
                "typical_dosages": self._string_list(info.get("typical_dosages")),
                "common_frequencies": self._string_list(info.get("common_frequencies")),
            }
            enhanced.append(item)
        return enhanced

    def enhance_image(self, image_data: str, mime_type: str = "image/jpeg") -> dict[str, Any]:
        return self._image_processor.enhance_data_url(image_data, mime_type)

    def suggest_medicines(self, query: str, *, dosage_hint: str = "", frequency_hint: str = "", limit: int = 5) -> list[dict[str, Any]]:
        normalized = self._normalize_name(query)
        if not normalized:
            return []

        suggestions: list[dict[str, Any]] = []
        for entry in self._combined_medicine_db():
            match_strength = self._score_medicine_match(normalized, entry, dosage_hint=dosage_hint, frequency_hint=frequency_hint)
            if match_strength <= 15:
                continue
            suggestions.append(
                {
                    "medicine_name": entry["name"],
                    "generic_name": entry.get("generic_name", ""),
                    "category": entry.get("category", ""),
                    "classification": entry.get("classification", ""),
                    "match_strength": match_strength,
                    "typical_dosages": entry.get("typical_dosages", []),
                    "common_frequencies": entry.get("common_frequencies", []),
                    "alternatives": entry.get("brand_alternatives", []),
                }
            )
        suggestions.sort(key=lambda item: item["match_strength"], reverse=True)
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in suggestions:
            key = item["medicine_name"].lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def search_medicine_database(self, query: str = "", limit: int = 25) -> list[dict[str, Any]]:
        rows = self._combined_medicine_db()
        if query.strip():
            matches = self.suggest_medicines(query, limit=limit)
            names = {item["medicine_name"].lower() for item in matches}
            ordered = [item for item in rows if item["name"].lower() in names]
            if ordered:
                return ordered[:limit]
        return rows[:limit]

    def submit_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        medicine_name = str(payload.get("medicine_name") or "").strip()
        note = str(payload.get("note") or "").strip()
        logger.info("Prescription decoder feedback medicine=%s note=%s", medicine_name or "unknown", note or "none")
        return {"success": True, "message": "Feedback recorded for decoder review."}

    def _build_decoder_prompt(self) -> str:
        return (
            "You are a careful medical prescription reading AI for India. Read this handwritten prescription image. "
            "Do not hallucinate certainty. Focus on medicine names, dosage amount, unit, frequency, duration, and instructions.\n\n"
            "Return only valid JSON with this exact schema:\n"
            "{\n"
            '  "doctor_name": "",\n'
            '  "patient_name": "",\n'
            '  "date": "",\n'
            '  "medicines": [\n'
            "    {\n"
            '      "medicine_name": "",\n'
            '      "dosage": {\n'
            '        "amount": "",\n'
            '        "unit": "",\n'
            '        "frequency": "",\n'
            '        "duration": "",\n'
            '        "instructions": ""\n'
            "      },\n"
            '      "raw_line_text": "",\n'
            '      "confidence": 0\n'
            "    }\n"
            "  ],\n"
            '  "raw_decoded_text": "",\n'
            '  "unreadable_parts": [],\n'
            '  "confidence_overall": 0\n'
            "}\n\n"
            "Recognize abbreviations like OD, BD, TDS, QID, HS, SOS, PRN, stat. "
            "If dosage details are written outside the medicine line, still attach them when reasonably likely."
        )

    async def _call_gemini_with_image(self, prompt: str, image_data: str, mime_type: str) -> str:
        if not GEMINI_API_KEY or genai is None or types is None:
            raise RuntimeError("Gemini image recognition is unavailable.")

        payload_mime, raw_bytes = self._decode_data_url(image_data, mime_type)

        def _generate() -> str:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=raw_bytes, mime_type=payload_mime),
                ],
            )
            text = str(getattr(response, "text", "") or "").strip()
            if not text:
                raise RuntimeError("Gemini returned an empty handwriting response.")
            return text

        return await asyncio.to_thread(_generate)

    def _decode_data_url(self, image_data: str, fallback_mime: str) -> tuple[str, bytes]:
        raw = str(image_data or "").strip()
        if raw.startswith("data:") and ";base64," in raw:
            header, encoded = raw.split(",", 1)
            mime_type = header[5:].split(";", 1)[0].strip() or fallback_mime
            return mime_type, base64.b64decode(encoded.encode("utf-8"), validate=False)
        return fallback_mime, base64.b64decode(raw.encode("utf-8"), validate=False)

    def _normalize_payload(self, payload: dict[str, Any], enhancement: dict[str, Any]) -> dict[str, Any]:
        medicines: list[dict[str, Any]] = []
        for item in payload.get("medicines", []) or []:
            if not isinstance(item, dict):
                continue
            parsed = self._normalize_medicine_item(item, enhancement)
            if parsed["medicine_name"] or parsed["raw_line_text"]:
                medicines.append(parsed)
        unreadable_parts = self._string_list(payload.get("unreadable_parts"))
        return {
            "doctor_name": str(payload.get("doctor_name") or "").strip(),
            "patient_name": str(payload.get("patient_name") or "").strip(),
            "date": str(payload.get("date") or "").strip(),
            "medicines": medicines,
            "raw_decoded_text": str(payload.get("raw_decoded_text") or "").strip(),
            "unreadable_parts": unreadable_parts,
            "confidence_overall": max(0, min(100, int(payload.get("confidence_overall", 0) or 0))),
            "source_image_quality": enhancement["source_image_quality"],
        }

    def _normalize_medicine_item(self, item: dict[str, Any], enhancement: dict[str, Any]) -> dict[str, Any]:
        raw_name = str(item.get("medicine_name") or "").strip()
        raw_line_text = str(item.get("raw_line_text") or "").strip()
        dosage_payload = item.get("dosage") if isinstance(item.get("dosage"), dict) else {}
        dosage_text = str(item.get("dosage") or "").strip() if not dosage_payload else ""
        frequency_text = str(item.get("frequency") or "").strip()
        duration_text = str(item.get("duration") or "").strip()
        instructions_text = str(item.get("special_instructions") or item.get("instructions") or "").strip()

        dosage = self._extract_dosage_details(
            " ".join(
                part
                for part in [
                    raw_name,
                    raw_line_text,
                    dosage_text,
                    str(dosage_payload.get("amount") or ""),
                    str(dosage_payload.get("unit") or ""),
                    str(dosage_payload.get("frequency") or ""),
                    str(dosage_payload.get("duration") or ""),
                    str(dosage_payload.get("instructions") or ""),
                    frequency_text,
                    duration_text,
                    instructions_text,
                ]
                if part
            )
        )

        if dosage_payload:
            dosage["amount"] = str(dosage_payload.get("amount") or dosage["amount"]).strip()
            dosage["unit"] = str(dosage_payload.get("unit") or dosage["unit"]).strip()
            dosage["frequency"] = str(dosage_payload.get("frequency") or dosage["frequency"]).strip()
            dosage["duration"] = str(dosage_payload.get("duration") or dosage["duration"]).strip()
            dosage["instructions"] = str(dosage_payload.get("instructions") or dosage["instructions"]).strip()
        if frequency_text and not dosage["frequency"]:
            dosage["frequency"] = self._humanize_frequency(frequency_text)
        if duration_text and not dosage["duration"]:
            dosage["duration"] = duration_text
        if instructions_text and not dosage["instructions"]:
            dosage["instructions"] = instructions_text

        suggestions = self.suggest_medicines(
            raw_name or raw_line_text,
            dosage_hint=f"{dosage['amount']} {dosage['unit']}".strip(),
            frequency_hint=dosage["frequency"],
            limit=5,
        )
        best_match = suggestions[0] if suggestions else None
        medicine_name = best_match["medicine_name"] if best_match and raw_name else raw_name
        alternatives = [item["medicine_name"] for item in suggestions if item["medicine_name"] != medicine_name][:5]

        name_match_strength = int(best_match["match_strength"]) if best_match else 20
        dosage_match_strength = self._dosage_pattern_score(dosage, best_match)
        image_quality = int(enhancement["source_image_quality"])
        ai_confidence = max(0, min(100, int(item.get("confidence", 0) or 0)))
        handwriting_clarity = int(enhancement["image_quality_breakdown"]["handwriting_clarity_score"])
        confidence_breakdown = {
            "ai_confidence": ai_confidence,
            "image_quality_score": image_quality,
            "handwriting_clarity_score": handwriting_clarity,
            "medicine_name_match_strength": name_match_strength,
            "dosage_pattern_match_strength": dosage_match_strength,
        }
        confidence = round(
            (ai_confidence * 0.28)
            + (image_quality * 0.16)
            + (handwriting_clarity * 0.16)
            + (name_match_strength * 0.24)
            + (dosage_match_strength * 0.16)
        )
        requires_verification = confidence < 70 or not medicine_name or name_match_strength < 45

        return {
            "medicine_name": medicine_name,
            "alternatives": alternatives,
            "confidence": max(0, min(100, int(confidence))),
            "confidence_breakdown": confidence_breakdown,
            "dosage": dosage,
            "dosage_text": " ".join(part for part in [dosage["amount"], dosage["unit"]] if part).strip(),
            "frequency": dosage["frequency"],
            "duration": dosage["duration"],
            "special_instructions": dosage["instructions"],
            "source_image_quality": image_quality,
            "requires_verification": requires_verification,
            "classification": best_match.get("classification", "") if best_match else "",
            "category": best_match.get("category", "") if best_match else "",
            "raw_line_text": raw_line_text,
        }

    def _extract_dosage_details(self, text: str) -> dict[str, str]:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        lower = cleaned.lower()
        amount = ""
        unit = ""
        dosage_match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|gm|g|ml|tablet(?:s)?|tab|capsule(?:s)?|cap|drop(?:s)?|sachet(?:s)?|tsp)", lower)
        if dosage_match:
            amount = dosage_match.group(1)
            unit = dosage_match.group(2).replace("tab", "tablet").replace("cap", "capsule")

        frequency = ""
        for token, human in FREQUENCY_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", lower):
                frequency = human
                break
        if not frequency:
            human_match = re.search(r"\b(once daily|twice daily|three times daily|four times daily|daily|weekly)\b", lower)
            if human_match:
                frequency = human_match.group(1).title()

        duration = ""
        duration_match = re.search(r"(\d+\s*(?:day|days|week|weeks|month|months))", lower)
        if duration_match:
            duration = duration_match.group(1)

        instructions = ""
        for pattern in INSTRUCTION_PATTERNS:
            if pattern in lower:
                instructions = pattern.title()
                break

        return {
            "amount": amount,
            "unit": unit,
            "frequency": frequency,
            "duration": duration,
            "instructions": instructions,
        }

    def _score_medicine_match(self, query: str, entry: dict[str, Any], *, dosage_hint: str = "", frequency_hint: str = "") -> int:
        candidates = [entry["name"], entry.get("generic_name", ""), *entry.get("aliases", [])]
        normalized_candidates = [self._normalize_name(candidate) for candidate in candidates if candidate]
        ratios = [int(SequenceMatcher(None, query, candidate).ratio() * 100) for candidate in normalized_candidates if candidate]
        if not ratios:
            return 0
        score = max(ratios)

        close_matches = get_close_matches(query, normalized_candidates, n=1, cutoff=0.6)
        if close_matches:
            score = max(score, 72)

        if dosage_hint:
            dosage_hint_normalized = dosage_hint.lower().replace(" ", "")
            if any(dosage_hint_normalized and dosage_hint_normalized in item.lower().replace(" ", "") for item in entry.get("typical_dosages", [])):
                score += 10
        if frequency_hint:
            frequency_hint_upper = frequency_hint.upper()
            if any(
                frequency_hint_upper.startswith(token)
                or token in frequency_hint_upper
                or frequency_hint_upper in token
                for token in entry.get("common_frequencies", [])
            ):
                score += 8
        if any(token in query for token in self._normalize_name(entry["name"]).split()):
            score += 5
        return max(0, min(100, score))

    def _dosage_pattern_score(self, dosage: dict[str, str], best_match: dict[str, Any] | None) -> int:
        score = 35
        if dosage["amount"] and dosage["unit"]:
            score += 20
        if dosage["frequency"]:
            score += 15
        if dosage["duration"]:
            score += 10
        if dosage["instructions"]:
            score += 8
        if best_match:
            typicals = " ".join(best_match.get("typical_dosages", []))
            common_frequencies = " ".join(best_match.get("common_frequencies", []))
            compact = f"{dosage['amount']}{dosage['unit']}".replace(" ", "").lower()
            if compact and compact in typicals.replace(" ", "").lower():
                score += 10
            if dosage["frequency"] and dosage["frequency"].split()[0].upper() in common_frequencies.upper():
                score += 10
        return max(0, min(100, score))

    def _calculate_overall_confidence(self, payload: dict[str, Any]) -> int:
        meds = payload.get("medicines", []) or []
        medicine_confidence = round(sum(int(item.get("confidence", 0) or 0) for item in meds) / len(meds)) if meds else 0
        image_quality = int(payload.get("source_image_quality", 0) or 0)
        unreadable_penalty = min(25, len(payload.get("unreadable_parts", [])) * 6)
        base = round((medicine_confidence * 0.68) + (image_quality * 0.32))
        return max(0, min(100, base - unreadable_penalty))

    def _fallback_payload(self, warning: str, unreadable_parts: list[str], enhancement: dict[str, Any]) -> dict[str, Any]:
        return {
            "doctor_name": "",
            "patient_name": "",
            "date": "",
            "medicines": [],
            "raw_decoded_text": warning,
            "unreadable_parts": unreadable_parts,
            "confidence_overall": max(15, enhancement["source_image_quality"] // 3),
            "source_image_quality": enhancement["source_image_quality"],
            "image_quality_breakdown": enhancement["image_quality_breakdown"],
            "applied_preprocessing": enhancement["applied_steps"],
            "enhanced_preview": enhancement["image_data"],
            "requires_verification": True,
        }

    def _fallback_medicine_info(self, medicine_name: str) -> dict[str, Any]:
        entry = self._find_local_entry(medicine_name)
        if entry:
            return {
                "uses": self._derive_uses(entry),
                "side_effects": self._derive_side_effects(entry),
                "prescription_required": entry.get("category") == "allopathy" and entry.get("classification") == "antibiotic",
                "category": entry.get("category", ""),
                "typical_dosages": entry.get("typical_dosages", []),
                "common_frequencies": entry.get("common_frequencies", []),
            }

        base = self._medicine_analyzer.find_medicine_info(medicine_name)
        return {
            "uses": self._split_text_field(base.get("uses", "")),
            "side_effects": self._split_text_field(base.get("side_effects", "")),
            "prescription_required": False,
            "category": "",
            "typical_dosages": [],
            "common_frequencies": [],
        }

    def _derive_uses(self, entry: dict[str, Any]) -> list[str]:
        classification = entry.get("classification", "")
        if classification == "antibiotic":
            return ["Used in doctor-directed bacterial infection treatment."]
        if classification == "analgesic":
            return ["Pain relief", "Fever relief"]
        if classification == "gastrointestinal":
            return ["Acidity and reflux support"]
        if classification == "adaptogen":
            return ["Stress support", "Daily vitality support"]
        if classification == "digestive":
            return ["Digestive support", "Bowel regularity support"]
        return ["Medicine information should be verified by a clinician."]

    def _derive_side_effects(self, entry: dict[str, Any]) -> list[str]:
        classification = entry.get("classification", "")
        if classification == "antibiotic":
            return ["Nausea", "Loose stools", "Stomach upset"]
        if classification == "analgesic":
            return ["Stomach upset", "Rare liver stress if overused"]
        if classification == "antihistamine":
            return ["Drowsiness", "Dry mouth"]
        return ["Side effects vary by patient and formulation."]

    def _load_local_medicine_db(self) -> list[dict[str, Any]]:
        path = Path(__file__).resolve().parents[1] / "data" / "medicine_decoder_db.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [self._normalize_db_entry(item) for item in payload if isinstance(item, dict)]
        except Exception as exc:
            logger.warning("Could not load decoder medicine DB: %s", exc)
        return []

    def _combined_medicine_db(self) -> list[dict[str, Any]]:
        rows = list(self._local_medicine_db)
        db = None
        try:
            db = SessionLocal()
            medicines = (
                db.query(MasterMedicine)
                .filter(MasterMedicine.is_active.is_(True))
                .order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.name.asc())
                .limit(150)
                .all()
            )
            for item in medicines:
                rows.append(
                    self._normalize_db_entry(
                        {
                            "name": item.name,
                            "generic_name": item.generic_name or "",
                            "aliases": [item.brand] if item.brand else [],
                            "category": item.category or "",
                            "classification": item.category or "",
                            "typical_dosages": self._extract_strengths_from_name(item.name),
                            "common_frequencies": [],
                            "instructions": [],
                            "brand_alternatives": [item.brand] if item.brand else [],
                        }
                    )
                )
        except Exception:
            pass
        finally:
            if db is not None:
                db.close()
        return rows

    def _normalize_db_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": str(entry.get("name") or "").strip(),
            "generic_name": str(entry.get("generic_name") or "").strip(),
            "aliases": self._string_list(entry.get("aliases")),
            "category": str(entry.get("category") or "").strip(),
            "classification": str(entry.get("classification") or "").strip(),
            "typical_dosages": self._string_list(entry.get("typical_dosages")),
            "common_frequencies": self._string_list(entry.get("common_frequencies")),
            "instructions": self._string_list(entry.get("instructions")),
            "brand_alternatives": self._string_list(entry.get("brand_alternatives")),
        }

    def _find_local_entry(self, medicine_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_name(medicine_name)
        matches = self.suggest_medicines(normalized, limit=1)
        if not matches:
            return None
        best_name = matches[0]["medicine_name"].lower()
        for entry in self._combined_medicine_db():
            if entry["name"].lower() == best_name:
                return entry
        return None

    def _extract_strengths_from_name(self, name: str) -> list[str]:
        return re.findall(r"\d+(?:\.\d+)?\s*(?:mg|mcg|gm|g|ml)", str(name or ""), flags=re.IGNORECASE)

    def _humanize_frequency(self, value: str) -> str:
        token = str(value or "").strip().lower()
        return FREQUENCY_MAP.get(token, str(value or "").strip())

    def _compose_raw_text(self, medicines: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for item in medicines:
            dosage = item.get("dosage", {})
            descriptor = ", ".join(
                part
                for part in [
                    " ".join([str(dosage.get("amount") or "").strip(), str(dosage.get("unit") or "").strip()]).strip(),
                    str(dosage.get("frequency") or "").strip(),
                    str(dosage.get("duration") or "").strip(),
                    str(dosage.get("instructions") or "").strip(),
                ]
                if part
            )
            lines.append(f"{item.get('medicine_name', 'Unclear medicine')}: {descriptor}".strip(": "))
        return "\n".join(line for line in lines if line)

    def _split_text_field(self, value: str) -> list[str]:
        parts = [item.strip() for item in re.split(r"[;,]\s*", str(value or "").strip()) if item.strip()]
        return parts[:4]

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if str(value or "").strip():
            return [str(value).strip()]
        return []

    def _normalize_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()
