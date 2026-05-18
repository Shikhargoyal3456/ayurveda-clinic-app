from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import DIRECT_ORDER_EVENTS, log_event, log_route_errors
from app.auth import ensure_csrf_token, verify_csrf
from app.config import settings
from app.database import get_db
from models.ai_features import AIPrescriptionScan
from models.prescription import Prescription
from services import ai_provider


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


def _dedupe_suggestions(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(text)
    return normalized[:6]


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
            "precautions": ["Symptoms are required before requesting AI suggestions."],
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }

    try:
        system_prompt = (
            "You suggest pharmacy medicine options for a medicine ordering UI. "
            "Return JSON only with keys suggested_medicines and precautions. "
            "suggested_medicines must be an array of 3 to 5 concise medicine names or medicine categories, "
            "including both allopathy and Ayurveda options where appropriate. "
            "precautions must be an array of concise safety notes. Do not diagnose and do not claim certainty."
        )
        detailed_prompt = (
            f"Patient symptoms: {cleaned_symptoms}\n\n"
            "Suggest 3 to 5 relevant medicine options. Include OTC options where appropriate. "
            "If prescription medicines may be relevant, mention that doctor review is needed.\n\n"
            'Return JSON like {"suggested_medicines":[""],"precautions":[""]}.'
        )
        simpler_prompt = (
            f"Symptoms: {cleaned_symptoms}\n"
            'Return JSON with suggested_medicines and precautions only.'
        )
        parsed, provider = await ai_provider.call_ai_json_with_retry(
            system_prompt=system_prompt,
            user_prompt=detailed_prompt,
            simpler_user_prompt=simpler_prompt,
            temperature=0.2,
            max_output_tokens=900,
        )

        suggested_medicines = parsed.get("suggested_medicines") or parsed.get("medicines") or []
        precautions = parsed.get("precautions") or []
        suggestions = _dedupe_suggestions(_string_list(suggested_medicines))

        return {
            "suggested_medicines": suggestions,
            "precautions": _string_list(precautions),
            "provider": provider,
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }
    except Exception as exc:
        logger.exception("Direct medicine AI suggestion failed: %s", exc)
        return JSONResponse(
            {
                "suggested_medicines": [],
                "precautions": [],
                "provider": "error",
                "error": str(exc),
                "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
            },
            status_code=503,
        )
