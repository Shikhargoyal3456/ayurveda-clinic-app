from __future__ import annotations

from threading import Lock
from typing import Any
from collections import Counter

from app.analytics import log_event
from services.analytics_service import load_events


_SUBSCRIPTIONS: list[dict[str, Any]] = []
_LOCK = Lock()


def create_subscription(user_id: str, medicines: list[str], frequency: str) -> dict[str, Any]:
    try:
        clean_user_id = str(user_id or "").strip()
        clean_medicines = [str(item).strip() for item in medicines if str(item).strip()]
        clean_frequency = str(frequency or "monthly").strip().lower() or "monthly"
        if not clean_user_id or not clean_medicines:
            return {"success": False, "error": "user_id_and_medicines_required"}
        subscription = {
            "id": f"sub_{len(_SUBSCRIPTIONS) + 1}",
            "user_id": clean_user_id,
            "medicines": clean_medicines,
            "frequency": clean_frequency,
            "active": True,
        }
        with _LOCK:
            _SUBSCRIPTIONS.append(subscription)
        log_event("subscription_created", {"subscription_id": subscription["id"], "user_id": clean_user_id})
        return {"success": True, "subscription": dict(subscription)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_user_subscriptions(user_id: str) -> list[dict[str, Any]]:
    try:
        clean_user_id = str(user_id or "").strip()
        with _LOCK:
            return [dict(item) for item in _SUBSCRIPTIONS if item.get("user_id") == clean_user_id]
    except Exception:
        return []


def get_all_subscriptions() -> list[dict[str, Any]]:
    try:
        with _LOCK:
            return [dict(item) for item in _SUBSCRIPTIONS]
    except Exception:
        return []


def trigger_refill() -> dict[str, Any]:
    try:
        subscriptions = get_all_subscriptions()
        log_event("subscription_refill_triggered", {"count": len(subscriptions)})
        return {"success": True, "triggered": len(subscriptions), "subscriptions": subscriptions}
    except Exception:
        return {"success": False, "triggered": 0, "subscriptions": []}


def get_subscription_recommendations(user_id: str | None = None) -> list[dict[str, str]]:
    try:
        counts: Counter[str] = Counter()
        for event in load_events():
            event_name = str(event.get("event_name") or "")
            if event_name not in {"medicine_added_to_cart", "order_created"}:
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if user_id and str(data.get("user_id") or data.get("patient_id") or "") not in {"", str(user_id)}:
                continue
            medicine = str(data.get("medicine_name") or data.get("medicine") or "").strip()
            if medicine:
                counts[medicine] += 1
        recommendations = [
            {"medicine": name, "recommended_frequency": "monthly"}
            for name, _ in counts.most_common(5)
        ]
        if recommendations:
            log_event("subscription_recommended", {"user_id": user_id or "all", "count": len(recommendations)})
        return recommendations
    except Exception:
        return []
