from __future__ import annotations

from dataclasses import dataclass


EMERGENCY_KEYWORDS = [
    "chest pain",
    "difficulty breathing",
    "breathlessness",
    "shortness of breath",
    "unconscious",
    "loss of consciousness",
    "fainted",
    "fainting",
    "stroke",
    "slurred speech",
    "one-sided weakness",
    "severe bleeding",
    "bleeding heavily",
    "seizure",
    "convulsion",
    "suicidal",
    "suicide",
    "overdose",
]

URGENT_KEYWORDS = [
    "high fever",
    "persistent vomiting",
    "dehydration",
    "blood pressure very high",
    "severe pain",
    "worsening rapidly",
    "can't eat",
    "cannot eat",
    "can't sleep",
    "panic attack",
    "pregnant and bleeding",
]


@dataclass
class EmergencyAssessment:
    severity: str
    ai_tag: str
    fallback_tag: str | None
    matched_keywords: list[str]


def _normalize_tag(tag: str | None) -> str:
    normalized = str(tag or "NORMAL").strip().upper()
    if normalized not in {"EMERGENCY", "URGENT", "NORMAL"}:
        return "NORMAL"
    return normalized


def assess_emergency(text: str, ai_tag: str | None = None) -> EmergencyAssessment:
    haystack = str(text or "").strip().lower()
    matched_emergency = [term for term in EMERGENCY_KEYWORDS if term in haystack]
    matched_urgent = [term for term in URGENT_KEYWORDS if term in haystack]
    normalized_ai_tag = _normalize_tag(ai_tag)

    if normalized_ai_tag == "EMERGENCY" or matched_emergency:
        return EmergencyAssessment(
            severity="emergency",
            ai_tag=normalized_ai_tag,
            fallback_tag="EMERGENCY" if matched_emergency else None,
            matched_keywords=matched_emergency,
        )
    if normalized_ai_tag == "URGENT" or matched_urgent:
        return EmergencyAssessment(
            severity="urgent",
            ai_tag=normalized_ai_tag,
            fallback_tag="URGENT" if matched_urgent else None,
            matched_keywords=matched_urgent,
        )
    return EmergencyAssessment(
        severity="normal",
        ai_tag=normalized_ai_tag,
        fallback_tag=None,
        matched_keywords=[],
    )
