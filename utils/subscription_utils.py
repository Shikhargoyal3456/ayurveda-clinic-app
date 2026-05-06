from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import razorpay
except ImportError:  # pragma: no cover
    razorpay = None
from sqlalchemy.orm import Session, object_session
from sqlalchemy import inspect, text

from app.config import settings
from app.database import SessionLocal, commit_with_retry
from app.models import Doctor
from models.subscription import (
    ClinicSubscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SubscriptionUsage,
    default_trial_end_date,
)


TRIAL_LENGTH_DAYS = 14
PUBLIC_TO_INTERNAL_PLAN = {
    SubscriptionPlan.FREE.value: SubscriptionPlan.FREE.value,
    "pro": SubscriptionPlan.BASIC.value,
    "enterprise": SubscriptionPlan.PRO.value,
    SubscriptionPlan.BASIC.value: SubscriptionPlan.BASIC.value,
    SubscriptionPlan.PRO.value: SubscriptionPlan.PRO.value,
}
INTERNAL_TO_PUBLIC_PLAN = {
    SubscriptionPlan.FREE.value: SubscriptionPlan.FREE.value,
    SubscriptionPlan.BASIC.value: "pro",
    SubscriptionPlan.PRO.value: "enterprise",
    "enterprise": "enterprise",
}
MONTHLY_PLAN_CATALOG: dict[str, dict[str, Any]] = {
    SubscriptionPlan.FREE.value: {
        "id": SubscriptionPlan.FREE.value,
        "name": "Free",
        "price_inr": 0,
        "billing_interval": "trial",
        "trial_days": TRIAL_LENGTH_DAYS,
    },
    SubscriptionPlan.BASIC.value: {
        "id": SubscriptionPlan.BASIC.value,
        "name": "Pro",
        "price_inr": 499,
        "billing_interval": "monthly",
        "trial_days": 0,
    },
    SubscriptionPlan.PRO.value: {
        "id": SubscriptionPlan.PRO.value,
        "name": "Enterprise",
        "price_inr": 999,
        "billing_interval": "monthly",
        "trial_days": 0,
    },
}

FEATURE_LIMITS: dict[str, dict[str, int | None]] = {
    SubscriptionPlan.FREE.value: {
        "ai_call": None,
        "voice": None,
        "patients": None,
        "prescription": None,
    },
    SubscriptionPlan.BASIC.value: {
        "ai_call": 200,
        "voice": 50,
        "patients": None,
        "prescription": None,
    },
    SubscriptionPlan.PRO.value: {
        "ai_call": None,
        "voice": None,
        "patients": None,
        "prescription": None,
    },
}

USAGE_FIELD_MAP = {
    "ai_call": "ai_calls_used",
    "voice": "voice_used",
    "patients": "patients_created",
    "prescription": "prescriptions_created",
}

PLAN_SUGGESTIONS = {
    "ai_call": "enterprise",
    "voice": "enterprise",
    "patients": "pro",
    "prescription": "pro",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def current_usage_month(now: datetime | None = None) -> str:
    active_now = now or utc_now()
    return active_now.strftime("%Y-%m")


def public_plan_id(plan_id: str) -> str:
    normalized = (plan_id or "").strip().lower()
    return INTERNAL_TO_PUBLIC_PLAN.get(normalized, normalized)


def internal_plan_id(plan_id: str) -> str:
    normalized = (plan_id or "").strip().lower()
    return PUBLIC_TO_INTERNAL_PLAN.get(normalized, normalized)


def list_seed_plans() -> list[dict[str, Any]]:
    return [
        {
            **MONTHLY_PLAN_CATALOG[plan_id],
            "id": public_plan_id(plan_id),
            "internal_plan_id": plan_id,
            "limits": _serialize_limits(FEATURE_LIMITS[plan_id]),
        }
        for plan_id in (SubscriptionPlan.FREE.value, SubscriptionPlan.BASIC.value, SubscriptionPlan.PRO.value)
    ]


def _serialize_limits(limits: dict[str, int | None]) -> dict[str, int | str]:
    return {key: ("unlimited" if value is None else int(value)) for key, value in limits.items()}


def _plan_enum(plan_id: str) -> SubscriptionPlan:
    normalized = internal_plan_id(plan_id)
    if normalized not in MONTHLY_PLAN_CATALOG:
        raise ValueError(f"Unsupported plan_id '{plan_id}'.")
    return SubscriptionPlan(normalized)


def _status_value(status: SubscriptionStatus | str) -> str:
    return status.value if isinstance(status, SubscriptionStatus) else str(status)


def _plan_value(plan: SubscriptionPlan | str) -> str:
    return plan.value if isinstance(plan, SubscriptionPlan) else str(plan)


def _resolve_db_session(user: Doctor) -> tuple[Session, bool]:
    bound_session = object_session(user)
    if bound_session is not None:
        return bound_session, False
    return SessionLocal(), True


def ensure_subscription_schema(db: Session) -> None:
    bind = db.get_bind()
    if bind is None:
        return
    ClinicSubscription.__table__.create(bind=bind, checkfirst=True)
    SubscriptionUsage.__table__.create(bind=bind, checkfirst=True)
    try:
        inspector = inspect(bind)
        columns = {column["name"] for column in inspector.get_columns("clinic_subscriptions")}
        if not {"user_id", "plan_id", "trial_end_date", "razorpay_subscription_id", "current_period_end"} <= columns:
            if "user_id" not in columns:
                db.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN user_id INTEGER"))
                if "doctor_id" in columns:
                    db.execute(text("UPDATE clinic_subscriptions SET user_id = doctor_id WHERE user_id IS NULL"))
            if "plan_id" not in columns:
                db.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN plan_id VARCHAR(20) DEFAULT 'free'"))
                if "plan" in columns:
                    db.execute(text("UPDATE clinic_subscriptions SET plan_id = plan WHERE plan_id IS NULL OR plan_id = 'free'"))
            if "trial_end_date" not in columns:
                db.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN trial_end_date DATE"))
            if "razorpay_subscription_id" not in columns:
                db.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN razorpay_subscription_id VARCHAR(100)"))
            if "current_period_end" not in columns:
                db.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN current_period_end DATETIME"))
                if "expires_at" in columns:
                    db.execute(text("UPDATE clinic_subscriptions SET current_period_end = expires_at WHERE current_period_end IS NULL"))
            commit_with_retry(db)
    except Exception:
        db.rollback()
        raise


def ensure_free_trial_for_user(db: Session, user: Doctor) -> ClinicSubscription:
    ensure_subscription_schema(db)
    subscription = db.query(ClinicSubscription).filter(ClinicSubscription.user_id == user.id).first()
    if subscription is not None:
        return subscription

    subscription = ClinicSubscription(
        user_id=user.id,
        plan_id=SubscriptionPlan.FREE,
        status=SubscriptionStatus.TRIAL,
        started_at=utc_now(),
        trial_end_date=default_trial_end_date(),
    )
    db.add(subscription)
    commit_with_retry(db)
    db.refresh(subscription)
    return subscription


def seed_free_trials_for_existing_users(db: Session) -> dict[str, int]:
    ensure_subscription_schema(db)
    existing_ids = {
        int(item[0]) for item in db.query(ClinicSubscription.user_id).all()
    }
    missing_query = db.query(Doctor)
    if existing_ids:
        missing_query = missing_query.filter(~Doctor.id.in_(existing_ids))
    missing_users = missing_query.all()
    created = 0
    now = utc_now()
    for user in missing_users:
        db.add(
            ClinicSubscription(
                user_id=user.id,
                plan_id=SubscriptionPlan.FREE,
                status=SubscriptionStatus.TRIAL,
                started_at=now,
                trial_end_date=(now + timedelta(days=TRIAL_LENGTH_DAYS)).date(),
            )
        )
        created += 1
    if created:
        commit_with_retry(db)
    return {"seeded": created}


def get_or_create_usage_record(db: Session, user: Doctor, month: str | None = None) -> SubscriptionUsage:
    ensure_subscription_schema(db)
    active_month = month or current_usage_month()
    usage = (
        db.query(SubscriptionUsage)
        .filter(SubscriptionUsage.user_id == user.id, SubscriptionUsage.month == active_month)
        .first()
    )
    if usage is not None:
        return usage

    usage = SubscriptionUsage(user_id=user.id, month=active_month)
    db.add(usage)
    commit_with_retry(db)
    db.refresh(usage)
    return usage


def _refresh_subscription_status(subscription: ClinicSubscription, now: datetime | None = None) -> ClinicSubscription:
    active_now = now or utc_now()
    if _plan_value(subscription.plan_id) == SubscriptionPlan.FREE.value:
        if subscription.trial_end_date and subscription.trial_end_date < active_now.date():
            subscription.status = SubscriptionStatus.EXPIRED
        elif _status_value(subscription.status) not in {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.CANCELED.value,
        }:
            subscription.status = SubscriptionStatus.TRIAL
    elif _status_value(subscription.status) == SubscriptionStatus.TRIAL.value:
        subscription.status = SubscriptionStatus.ACTIVE
    elif subscription.current_period_end and subscription.current_period_end < active_now:
        subscription.status = SubscriptionStatus.EXPIRED
    return subscription


def get_active_subscription(db: Session, user: Doctor) -> ClinicSubscription:
    subscription = ensure_free_trial_for_user(db, user)
    previous_status = _status_value(subscription.status)
    _refresh_subscription_status(subscription)
    if _status_value(subscription.status) != previous_status:
        commit_with_retry(db)
        db.refresh(subscription)
    return subscription


def check_subscription_access(user, feature: str) -> dict:
    normalized_feature = (feature or "").strip().lower()
    if normalized_feature not in USAGE_FIELD_MAP:
        return {
            "allowed": False,
            "reason": "unsupported_feature",
            "limit": 0,
            "used": 0,
            "upgrade_required": False,
        }

    db, created_session = _resolve_db_session(user)
    try:
        subscription = get_active_subscription(db, user)
        usage = get_or_create_usage_record(db, user)
        plan_id = _plan_value(subscription.plan_id)
        status = _status_value(subscription.status)
        limit = FEATURE_LIMITS[plan_id][normalized_feature]
        used = int(getattr(usage, USAGE_FIELD_MAP[normalized_feature], 0) or 0)

        if plan_id == SubscriptionPlan.FREE.value and status == SubscriptionStatus.EXPIRED.value:
            return {
                "allowed": False,
                "reason": "trial_expired",
                "limit": 0 if limit is None else int(limit),
                "used": used,
                "upgrade_required": True,
            }

        if status == SubscriptionStatus.CANCELED.value and plan_id != SubscriptionPlan.FREE.value:
            return {
                "allowed": False,
                "reason": "subscription_canceled",
                "limit": 0 if limit is None else int(limit),
                "used": used,
                "upgrade_required": True,
            }

        if limit is None:
            return {
                "allowed": True,
                "reason": "allowed",
                "limit": -1,
                "used": used,
                "upgrade_required": False,
            }

        if used >= int(limit):
            return {
                "allowed": False,
                "reason": "limit_exceeded",
                "limit": int(limit),
                "used": used,
                "upgrade_required": True,
            }

        return {
            "allowed": True,
            "reason": "allowed",
            "limit": int(limit),
            "used": used,
            "upgrade_required": False,
        }
    finally:
        if created_session:
            db.close()


def increment_subscription_usage(user: Doctor, feature: str) -> dict:
    normalized_feature = (feature or "").strip().lower()
    access = check_subscription_access(user, normalized_feature)
    if not access.get("allowed"):
        return access

    db, created_session = _resolve_db_session(user)
    try:
        usage = get_or_create_usage_record(db, user)
        field_name = USAGE_FIELD_MAP[normalized_feature]
        setattr(usage, field_name, int(getattr(usage, field_name, 0) or 0) + 1)
        commit_with_retry(db)
        used = int(getattr(usage, field_name, 0) or 0)
        return {
            **access,
            "used": used,
        }
    finally:
        if created_session:
            db.close()


def build_paywall_response(user: Doctor, feature: str) -> dict[str, Any]:
    access = check_subscription_access(user, feature)
    if access.get("allowed"):
        return {
            "allowed": True,
            **access,
        }

    reason = str(access.get("reason", "limit_exceeded"))
    message = "You've reached your free limit. Upgrade to continue."
    if reason == "trial_expired":
        message = "Your free trial has expired. Upgrade to continue."
    elif reason == "subscription_canceled":
        message = "Your subscription is canceled. Upgrade or reactivate to continue."

    return {
        "error": reason,
        "message": message,
        "upgrade_required": True,
        "plan_suggestion": PLAN_SUGGESTIONS.get((feature or "").strip().lower(), "enterprise"),
        "limit_exceeded": reason == "limit_exceeded",
        "trial_expired": reason == "trial_expired",
        "allowed": False,
        "reason": reason,
        "limit": access.get("limit", 0),
        "used": access.get("used", 0),
    }


def summarize_subscription_status(db: Session, user: Doctor) -> dict[str, Any]:
    seed_free_trials_for_existing_users(db)
    subscription = get_active_subscription(db, user)
    usage = get_or_create_usage_record(db, user)
    plan_id = _plan_value(subscription.plan_id)
    limits = FEATURE_LIMITS[plan_id]
    return {
        "subscription": {
            "plan_id": public_plan_id(plan_id),
            "internal_plan_id": plan_id,
            "status": _status_value(subscription.status),
            "trial_end_date": subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
            "razorpay_subscription_id": subscription.razorpay_subscription_id,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        },
        "usage": {
            "month": usage.month,
            "ai_calls_used": int(usage.ai_calls_used or 0),
            "voice_used": int(usage.voice_used or 0),
            "patients_created": int(usage.patients_created or 0),
            "prescriptions_created": int(usage.prescriptions_created or 0),
        },
        "limits": _serialize_limits(limits),
        "access": {
            feature: check_subscription_access(user, feature)
            for feature in USAGE_FIELD_MAP
        },
    }


def get_razorpay_client() -> razorpay.Client:
    if razorpay is None:
        raise RuntimeError("Razorpay SDK is not installed.")
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_or_fetch_remote_plan(plan_id: str) -> dict[str, Any]:
    plan_key = _plan_enum(plan_id).value
    if plan_key == SubscriptionPlan.FREE.value:
        raise ValueError("Free plan does not require Razorpay subscription creation.")

    catalog = MONTHLY_PLAN_CATALOG[plan_key]
    client = get_razorpay_client()
    normalized_name = f"Kash AI {catalog['name']} Monthly"

    existing_plans = client.plan.all({"count": 100}).get("items", [])
    for item in existing_plans:
        item_name = str(((item or {}).get("item") or {}).get("name", "")).strip()
        amount = int(((item or {}).get("item") or {}).get("amount", 0) or 0)
        period = str((item or {}).get("period", "")).strip()
        interval = int((item or {}).get("interval", 0) or 0)
        if item_name == normalized_name and amount == int(catalog["price_inr"]) * 100 and period == "monthly" and interval == 1:
            return item

    return client.plan.create(
        {
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": normalized_name,
                "description": f"{catalog['name']} monthly subscription",
                "amount": int(catalog["price_inr"]) * 100,
                "currency": "INR",
            },
            "notes": {
                "internal_plan_id": plan_key,
            },
        }
    )


def create_remote_subscription(user: Doctor, plan_id: str) -> dict[str, Any]:
    plan_key = _plan_enum(plan_id).value
    remote_plan = create_or_fetch_remote_plan(plan_key)
    client = get_razorpay_client()
    return client.subscription.create(
        {
            "plan_id": remote_plan["id"],
            "total_count": 120,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "user_id": str(user.id),
                "username": user.username,
                "internal_plan_id": plan_key,
            },
        }
    )


def verify_razorpay_subscription_signature(
    razorpay_payment_id: str,
    razorpay_subscription_id: str,
    razorpay_signature: str,
) -> bool:
    payload = f"{razorpay_payment_id}|{razorpay_subscription_id}".encode("utf-8")
    expected = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def update_subscription_from_checkout(
    db: Session,
    user: Doctor,
    plan_id: str,
    razorpay_subscription_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict[str, Any]:
    if not verify_razorpay_subscription_signature(
        razorpay_payment_id=razorpay_payment_id,
        razorpay_subscription_id=razorpay_subscription_id,
        razorpay_signature=razorpay_signature,
    ):
        return {
            "error": "verification_failed",
            "message": "Subscription verification failed.",
            "upgrade_required": False,
        }

    subscription = get_active_subscription(db, user)
    subscription.plan_id = _plan_enum(plan_id)
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.razorpay_subscription_id = razorpay_subscription_id
    subscription.current_period_end = utc_now() + timedelta(days=30)
    commit_with_retry(db)
    return {
        "success": True,
        "subscription_id": razorpay_subscription_id,
        "plan_id": public_plan_id(_plan_value(subscription.plan_id)),
        "internal_plan_id": _plan_value(subscription.plan_id),
        "status": _status_value(subscription.status),
    }


def apply_razorpay_webhook(
    db: Session,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    entity = (
        (((payload or {}).get("payload") or {}).get("subscription") or {}).get("entity")
        or (payload or {}).get("subscription")
        or {}
    )
    subscription_id = str((entity or {}).get("id", "")).strip()
    if not subscription_id:
        return {"processed": False, "reason": "subscription_missing"}

    subscription = (
        db.query(ClinicSubscription)
        .filter(ClinicSubscription.razorpay_subscription_id == subscription_id)
        .first()
    )
    if subscription is None:
        return {"processed": False, "reason": "local_subscription_missing", "subscription_id": subscription_id}

    event_key = (event_name or "").strip().lower()
    if event_key == "subscription.activated":
        subscription.status = SubscriptionStatus.ACTIVE
    elif event_key == "subscription.charged":
        subscription.status = SubscriptionStatus.ACTIVE
        current_end = (entity or {}).get("current_end")
        if current_end:
            subscription.current_period_end = datetime.fromtimestamp(int(current_end), tz=timezone.utc)
    elif event_key == "subscription.cancelled":
        subscription.status = SubscriptionStatus.CANCELED

    commit_with_retry(db)
    return {
        "processed": True,
        "event": event_key,
        "subscription_id": subscription_id,
        "status": _status_value(subscription.status),
    }


def cancel_user_subscription(db: Session, user: Doctor) -> dict[str, Any]:
    subscription = get_active_subscription(db, user)
    if not subscription.razorpay_subscription_id:
        subscription.status = SubscriptionStatus.CANCELED
        commit_with_retry(db)
        return {
            "success": True,
            "status": _status_value(subscription.status),
            "subscription_id": None,
        }

    client = get_razorpay_client()
    client.subscription.cancel(subscription.razorpay_subscription_id, {"cancel_at_cycle_end": 1})
    subscription.status = SubscriptionStatus.CANCELED
    commit_with_retry(db)
    return {
        "success": True,
        "status": _status_value(subscription.status),
        "subscription_id": subscription.razorpay_subscription_id,
    }
