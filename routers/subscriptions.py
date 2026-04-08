from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_doctor
from app.config import settings
from app.database import get_db
from app.models import Doctor
from utils.subscription_utils import (
    apply_razorpay_webhook,
    cancel_user_subscription,
    create_remote_subscription,
    list_seed_plans,
    seed_free_trials_for_existing_users,
    summarize_subscription_status,
    update_subscription_from_checkout,
)


router = APIRouter(tags=["subscriptions"])
logger = logging.getLogger(__name__)


@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    seed_result = seed_free_trials_for_existing_users(db)
    return JSONResponse(
        {
            "plans": list_seed_plans(),
            "seed": seed_result,
            "current_subscription": summarize_subscription_status(db, doctor)["subscription"],
        }
    )


@router.get("/subscription/status")
def subscription_status(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    seed_free_trials_for_existing_users(db)
    return JSONResponse(summarize_subscription_status(db, doctor))


@router.post("/subscribe/{plan_id}")
async def subscribe(
    plan_id: str,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    seed_free_trials_for_existing_users(db)
    normalized_plan = (plan_id or "").strip().lower()
    if normalized_plan not in {"basic", "pro"}:
        return JSONResponse(
            {
                "error": "invalid_plan",
                "message": "Choose a paid plan to subscribe.",
                "upgrade_required": False,
            },
            status_code=400,
        )

    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    razorpay_subscription_id = str(body.get("razorpay_subscription_id", "")).strip()
    razorpay_payment_id = str(body.get("razorpay_payment_id", "")).strip()
    razorpay_signature = str(body.get("razorpay_signature", "")).strip()

    if razorpay_subscription_id and razorpay_payment_id and razorpay_signature:
        return JSONResponse(
            update_subscription_from_checkout(
                db=db,
                user=doctor,
                plan_id=normalized_plan,
                razorpay_subscription_id=razorpay_subscription_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
            )
        )

    try:
        remote_subscription = create_remote_subscription(doctor, normalized_plan)
    except Exception as exc:
        logger.exception("Subscription creation failed for doctor_id=%s: %s", doctor.id, exc)
        return JSONResponse(
            {
                "error": "subscription_creation_failed",
                "message": "Unable to create Razorpay subscription right now.",
                "upgrade_required": False,
            },
            status_code=500,
        )

    return JSONResponse(
        {
            "subscription_id": remote_subscription.get("id"),
            "status": remote_subscription.get("status"),
            "plan_id": normalized_plan,
            "key_id": settings.razorpay_key_id,
            "checkout": {
                "subscription_id": remote_subscription.get("id"),
                "key": settings.razorpay_key_id,
                "name": "AyurvedaClinic.app",
                "description": f"{normalized_plan.title()} monthly subscription",
            },
        }
    )


@router.post("/webhook")
async def subscription_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    provided_signature = request.headers.get("X-Razorpay-Signature", "").strip()
    webhook_secret = settings.razorpay_key_secret

    if webhook_secret:
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, provided_signature):
            return JSONResponse(
                {
                    "error": "invalid_signature",
                    "message": "Webhook signature verification failed.",
                    "upgrade_required": False,
                },
                status_code=400,
            )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except ValueError:
        return JSONResponse(
            {
                "error": "invalid_payload",
                "message": "Webhook payload is not valid JSON.",
                "upgrade_required": False,
            },
            status_code=400,
        )

    return JSONResponse(apply_razorpay_webhook(db, str(payload.get("event", "")), payload))


@router.post("/cancel")
def cancel_subscription(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    seed_free_trials_for_existing_users(db)
    try:
        result = cancel_user_subscription(db, doctor)
    except Exception as exc:
        logger.exception("Subscription cancellation failed for doctor_id=%s: %s", doctor.id, exc)
        return JSONResponse(
            {
                "error": "cancel_failed",
                "message": "Unable to cancel subscription right now.",
                "upgrade_required": False,
            },
            status_code=500,
        )
    return JSONResponse(result)
