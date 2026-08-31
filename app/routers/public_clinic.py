from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings

try:
    import razorpay  # type: ignore
except Exception:  # pragma: no cover
    razorpay = None


router = APIRouter(tags=["public-clinic"])
logger = logging.getLogger(__name__)


class PublicAnalyzeRequest(BaseModel):
    symptoms: str


class PublicBookRequest(BaseModel):
    symptoms: str = ""
    amount: int = 29900
    currency: str = "INR"
    service: str = "ayurveda_consultation"


def _dosha_scores(symptoms: str) -> dict[str, int]:
    text = symptoms.lower()
    vata = 28
    pitta = 28
    kapha = 24

    if any(word in text for word in ("gas", "constipation", "dry", "anxiety", "insomnia", "pain", "stiff", "bloating")):
        vata += 28
    if any(word in text for word in ("acid", "acidity", "burn", "heat", "anger", "irrit", "rash", "headache")):
        pitta += 30
    if any(word in text for word in ("cold", "cough", "mucus", "heavy", "slow", "sleepy", "congestion", "swelling")):
        kapha += 30
    if any(word in text for word in ("stress", "sleep", "fatigue", "tired")):
        vata += 10
    if any(word in text for word in ("fever", "infection")):
        pitta += 12

    total = max(vata + pitta + kapha, 1)
    return {
        "Vata": round((vata / total) * 100),
        "Pitta": round((pitta / total) * 100),
        "Kapha": round((kapha / total) * 100),
    }


def _plan_for(dominant: str) -> dict[str, Any]:
    plans = {
        "Vata": {
            "treatment": (
                "Your symptoms suggest Vata aggravation. Focus on warmth, routine, gentle oil massage, "
                "early sleep, hydration, and easy-to-digest cooked meals."
            ),
            "diet": ["Warm cooked meals", "Moong dal khichdi", "Ghee in moderation"],
            "herbs": ["Ashwagandha", "Dashmool", "Triphala when constipated"],
            "medicines": ["Ashwagandha", "Triphala", "Mahanarayan oil"],
        },
        "Pitta": {
            "treatment": (
                "Your symptoms suggest Pitta aggravation. Focus on cooling foods, regular meals, "
                "avoiding excess spice, and calming digestion."
            ),
            "diet": ["Coconut water", "Amla", "Coriander and fennel water"],
            "herbs": ["Amla", "Guduchi", "Shatavari"],
            "medicines": ["Amla Juice", "Avipattikar Churna", "Guduchi tablets"],
        },
        "Kapha": {
            "treatment": (
                "Your symptoms suggest Kapha aggravation. Focus on light warm meals, movement, steam "
                "inhalation when congested, and avoiding excess cold or sweet foods."
            ),
            "diet": ["Warm soups", "Ginger tea", "Light early dinner"],
            "herbs": ["Tulsi", "Trikatu", "Sitopaladi"],
            "medicines": ["Tulsi drops", "Trikatu Churna", "Sitopaladi Churna"],
        },
    }
    return plans.get(dominant, plans["Vata"])


@router.post("/analyze")
async def public_analyze(payload: PublicAnalyzeRequest):
    # PUBLIC-CLINIC-1: Patient-friendly, no-login endpoint used by static/index.html.
    symptoms = payload.symptoms.strip()
    if not symptoms:
        return JSONResponse(status_code=400, content={"error": "Symptoms are required."})
    if len(symptoms) > 2000:
        return JSONResponse(status_code=400, content={"error": "Symptoms must be 2000 characters or fewer."})

    scores = _dosha_scores(symptoms)
    dominant = max(scores, key=scores.get)
    plan = _plan_for(dominant)
    return {
        "dosha_scores": scores,
        "dominant_dosha": dominant,
        "treatment": plan["treatment"],
        "diet": plan["diet"],
        "herbs": plan["herbs"],
        "medicines": plan["medicines"],
        "disclaimer": "This is wellness guidance only and does not replace a qualified clinician.",
    }


@router.post("/book")
async def public_book(payload: PublicBookRequest = Body(...)):
    # PUBLIC-CLINIC-1: Create a consultation payment order when Razorpay is configured.
    amount = payload.amount if payload.amount and payload.amount > 0 else 29900
    currency = (payload.currency or "INR").upper()
    if currency != "INR":
        return JSONResponse(status_code=400, content={"error": "Only INR payments are supported."})

    fallback = {
        "success": False,
        "message": "Consultation booking is available from the payment page.",
        "payment_url": "/payments/daily",
        "amount": amount,
        "currency": currency,
        "key_id": settings.razorpay_key_id,
    }

    if razorpay is None or not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return fallback

    try:
        client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        order = client.order.create(
            {
                "amount": amount,
                "currency": currency,
                "payment_capture": 1,
                "notes": {
                    "service": payload.service,
                    "source": "public_clinic",
                    "symptoms": payload.symptoms[:240],
                },
            }
        )
    except Exception as exc:
        logger.exception("Public consultation Razorpay order failed: %s", exc)
        return fallback

    return {
        "success": True,
        "key_id": settings.razorpay_key_id,
        "razorpay_order_id": order.get("id"),
        "amount": order.get("amount", amount),
        "currency": order.get("currency", currency),
        "service": payload.service,
    }
