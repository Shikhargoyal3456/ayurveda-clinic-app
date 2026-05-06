from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import DIRECT_ORDER_EVENTS, log_event, log_route_errors, track_error_event
from app.auth import ensure_csrf_token, verify_csrf
from app.config import settings
from app.database import get_db
from models.ai_features import AIPrescriptionScan
from models.prescription import Prescription
from services import ai_provider
from services.medicine_catalog import get_default_medicines


router = APIRouter(tags=["direct-medicine-ordering"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
logger = logging.getLogger(__name__)


@router.get("/medicines")
def medicines_entry_point():
    # POLISH-1-ORDER-BUTTONS: Keep the patient-friendly /medicines entry while reusing the existing route.
    return RedirectResponse(url="/order-medicines", status_code=307)


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("name") or item.get("medicine") or item.get("title") or "").strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


_AI_FALLBACK_PRECAUTIONS = [
    "Use over-the-counter medicines only as directed on the label.",
    "Consult a doctor if symptoms are severe, persistent, or worsening.",
]

_SYMPTOM_SUGGESTION_RULES: list[tuple[tuple[str, ...], list[str], list[str]]] = [
    (
        ("acidity", "acid", "heartburn", "gas", "bloating", "indigestion", "reflux", "stomach burn"),
        ["Avipattikar Churna", "Hingvastak Churna", "Triphala"],
        ["Avoid spicy or oily food until symptoms settle."],
    ),
    (
        ("fever", "temperature", "headache", "head pain", "body ache", "pain"),
        ["Paracetamol", "Giloy Tablet", "Tulsi Drops"],
        ["Check temperature and seek care for high fever or severe headache."],
    ),
    (
        ("cold", "cough", "sore throat", "throat", "congestion", "runny nose", "sneezing"),
        ["Sitopaladi Churna", "Tulsi Drops", "Mulethi Powder"],
        ["Seek medical advice for breathing difficulty, chest pain, or prolonged cough."],
    ),
    (
        ("weakness", "tired", "fatigue", "immunity", "low energy"),
        ["Chyawanprash", "Amla Juice", "Ashwagandha"],
        ["Persistent weakness can need clinical evaluation."],
    ),
    (
        ("stress", "sleep", "anxiety", "restless"),
        ["Ashwagandha", "Brahmi Vati"],
        ["Avoid sedating products before driving or operating machinery."],
    ),
    (
        ("skin", "acne", "pimple", "rash", "itch"),
        ["Neem Capsules", "Haridra Tablet"],
        ["Seek care quickly for spreading rash, swelling, or fever."],
    ),
    (
        ("joint", "muscle", "sprain", "back pain", "knee pain"),
        ["Diclofenac Gel", "Ibuprofen"],
        ["Avoid ibuprofen if you have ulcers, kidney disease, or blood thinner use unless advised."],
    ),
    (
        ("mouth", "gum", "tooth", "dental"),
        ["Chlorhexidine Mouthwash"],
        ["Dental pain or swelling should be checked by a dentist."],
    ),
]

_AI_CATEGORY_ALIASES: list[tuple[tuple[str, ...], list[str]]] = [
    (("antacid", "h2 blocker", "proton pump", "omeprazole", "famotidine"), ["Avipattikar Churna", "Hingvastak Churna"]),
    (("analgesic", "pain reliever", "acetaminophen"), ["Paracetamol"]),
    (("nsaid",), ["Ibuprofen", "Diclofenac Gel"]),
    (("cough", "expectorant"), ["Sitopaladi Churna", "Mulethi Powder"]),
]


def _catalog_names() -> set[str]:
    return {str(item.get("name") or "").strip() for item in get_default_medicines() if item.get("name")}


def _dedupe_suggestions(values: list[str]) -> list[str]:
    catalog_names = _catalog_names()
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        catalog_match = next((name for name in catalog_names if name.lower() == text.lower()), text)
        key = catalog_match.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(catalog_match)
    return normalized[:6]


def _rule_based_ai_help(symptoms: str) -> dict[str, list[str]]:
    text = symptoms.lower()
    suggestions: list[str] = []
    precautions: list[str] = []
    for triggers, rule_suggestions, rule_precautions in _SYMPTOM_SUGGESTION_RULES:
        if any(trigger in text for trigger in triggers):
            suggestions.extend(rule_suggestions)
            precautions.extend(rule_precautions)

    if not suggestions:
        suggestions = ["Chyawanprash", "Amla Juice", "Triphala"]

    return {
        "suggested_medicines": _dedupe_suggestions(suggestions),
        "precautions": _dedupe_suggestions(precautions + _AI_FALLBACK_PRECAUTIONS),
    }


def _catalog_friendly_suggestions(raw_suggestions: list[str], symptoms: str) -> list[str]:
    suggestions = _dedupe_suggestions(raw_suggestions)
    expanded: list[str] = []
    for suggestion in suggestions:
        lower = suggestion.lower()
        for aliases, replacements in _AI_CATEGORY_ALIASES:
            if any(alias in lower for alias in aliases):
                expanded.extend(replacements)
                break
        else:
            expanded.append(suggestion)

    fallback = _rule_based_ai_help(symptoms)["suggested_medicines"]
    catalog_names = _catalog_names()
    catalog_matches = [
        item
        for item in expanded
        if any(name.lower() == item.lower() or item.lower() in name.lower() for name in catalog_names)
    ]
    return _dedupe_suggestions(catalog_matches or fallback)


def _prefill_from_prescription(prescription: Prescription | None) -> list[dict[str, object]]:
    if prescription is None:
        return []
    medicines: list[dict[str, object]] = []
    try:
        for item in prescription.medicines or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            medicines.append(
                {
                    "name": name,
                    "qty": 1,
                    "dosage": str(item.get("dosage") or "").strip(),
                    "frequency": str(item.get("frequency") or "").strip(),
                    "prescription_required": True,
                }
            )
    except Exception as exc:
        logger.exception("Prescription prefill failed: %s", exc)
        return []
    return medicines


def _prefill_from_ai_prescription(prescription: AIPrescriptionScan | None) -> list[dict[str, object]]:
    if prescription is None or not isinstance(prescription.medicines, list):
        return []
    medicines: list[dict[str, object]] = []
    for item in prescription.medicines:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        medicines.append(
            {
                "name": name,
                "qty": int(item.get("suggested_quantity", 1) or 1),
                "dosage": str(item.get("dosage") or "").strip(),
                "frequency": str(item.get("duration") or item.get("frequency") or "").strip(),
                "prescription_required": True,
            }
        )
    return medicines


@router.get("/order-medicines")
def order_medicines_page(
    request: Request,
    source: str = "",
    prescription_id: int | None = None,
    q: str = "",
    tab: str = "",
    db: Session = Depends(get_db),
):
    prescription = None
    prefill_medicines: list[dict[str, object]] = []
    if source == "prescription" and prescription_id:
        try:
            prescription = db.get(Prescription, prescription_id)
            prefill_medicines = _prefill_from_prescription(prescription)
            if not prefill_medicines:
                ai_prescription = db.get(AIPrescriptionScan, prescription_id)
                prefill_medicines = _prefill_from_ai_prescription(ai_prescription)
            log_event("prescription_order_initiated", {"prescription_id": prescription_id})
        except Exception as exc:
            logger.exception("Prescription order prefill failed: %s", exc)
            prefill_medicines = []
    else:
        log_event("otc_order_initiated", {})
    log_event("order_medicines_page_viewed", {"source": source or "direct", "prescription_id": prescription_id})
    return templates.TemplateResponse(
        request,
        "order_medicines.html",
        {
            "request": request,
            "csrf_token": ensure_csrf_token(request),
            "prefill_medicines": prefill_medicines,
            "has_prescription": bool(prefill_medicines),
            "prefill_order_source": "prescription" if prefill_medicines else "manual",
            "prefill_prescription_id": prescription_id if prefill_medicines else "",
            "initial_query": q.strip(),
            "initial_tab": tab.strip().lower(),
        },
    )


@router.post("/order-medicines/track-event")
async def order_medicines_track_event(
    payload: dict[str, Any] = Body(...),
    _: None = Depends(verify_csrf),
):
    event = str(payload.get("event") or "").strip()
    if event not in DIRECT_ORDER_EVENTS:
        return {"ok": False, "error": "unsupported_event"}

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    log_event(event, metadata)
    return {"ok": True}


@router.post("/order-medicines/ai-suggest")
@log_route_errors("ai_failure", "/order-medicines/ai-suggest")
async def order_medicines_ai_suggest(
    symptoms: str = Form(...),
    _: None = Depends(verify_csrf),
):
    cleaned_symptoms = symptoms.strip()
    if not cleaned_symptoms:
        return {
            "suggested_medicines": [],
            "precautions": ["Describe your symptoms before requesting AI suggestions."],
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }

    try:
        raw_response, provider = await run_in_threadpool(
            ai_provider.chat_with_fallback,
            (
                "You suggest over-the-counter pharmacy medicine options for a medicine ordering UI. "
                "Return JSON only with keys suggested_medicines and precautions. "
                "suggested_medicines must be an array of concise medicine names or categories. "
                "precautions must be an array of concise safety notes. Do not diagnose."
            ),
            f"Symptoms: {cleaned_symptoms}",
            0.2,
            "application/json",
        )
        try:
            parsed = ai_provider.parse_json_response(raw_response)
        except ValueError:
            logger.warning("Direct medicine AI returned non-JSON response")
            parsed = {"suggested_medicines": [raw_response], "precautions": []}

        suggested_medicines = parsed.get("suggested_medicines") or parsed.get("medicines") or []
        precautions = parsed.get("precautions") or []
        fallback_help = _rule_based_ai_help(cleaned_symptoms)

        return {
            "suggested_medicines": _catalog_friendly_suggestions(_string_list(suggested_medicines), cleaned_symptoms),
            "precautions": _string_list(precautions) or fallback_help["precautions"],
            "provider": provider.value,
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }
    except Exception as exc:
        logger.exception("Direct medicine AI suggestion failed: %s", exc)
        track_error_event("ai_failure", "/order-medicines/ai-suggest", str(exc))
        fallback_help = _rule_based_ai_help(cleaned_symptoms)
        return {
            "suggested_medicines": fallback_help["suggested_medicines"],
            "precautions": ["AI suggestions are temporarily unavailable."] + fallback_help["precautions"],
            "provider": "fallback",
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }
