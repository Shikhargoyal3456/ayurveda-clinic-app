from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates

from app.analytics import DIRECT_ORDER_EVENTS, log_event, log_route_errors, track_error_event
from app.auth import ensure_csrf_token, verify_csrf
from app.config import settings
from services import ai_provider


router = APIRouter(tags=["direct-medicine-ordering"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
logger = logging.getLogger(__name__)


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


@router.get("/order-medicines")
def order_medicines_page(request: Request):
    return templates.TemplateResponse(
        "order_medicines.html",
        {"request": request, "csrf_token": ensure_csrf_token(request)},
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

        return {
            "suggested_medicines": _string_list(suggested_medicines),
            "precautions": _string_list(precautions),
            "provider": provider.value,
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }
    except Exception as exc:
        logger.exception("Direct medicine AI suggestion failed: %s", exc)
        track_error_event("ai_failure", "/order-medicines/ai-suggest", str(exc))
        return {
            "suggested_medicines": [],
            "precautions": ["AI suggestions are temporarily unavailable.", "Please consult a doctor"],
            "disclaimer": "AI suggestions are advisory. Consult a doctor if needed.",
        }
