from __future__ import annotations

import os
from threading import Lock
from typing import Any

from app.analytics import log_event
from services.feature_flags import is_delivery_enabled


_DELIVERIES: dict[str, dict[str, str]] = {}
_LOCK = Lock()


def assign_delivery(order_id: str | int) -> dict[str, str]:
    try:
        key = str(order_id)
        delivery = {
            "order_id": key,
            "partner": "Dunzo",
            "status": "assigned",
            "eta": "30 mins",
        }
        with _LOCK:
            _DELIVERIES[key] = delivery
        log_event("delivery_assigned", delivery)
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "partner": "Dunzo", "status": "unassigned", "eta": ""}


def assign_delivery_real(order_id: str | int) -> dict[str, str]:
    try:
        api_url = os.getenv("DELIVERY_API_URL", "").strip()
        if not api_url:
            raise ValueError("DELIVERY_API_URL is not configured")
        import requests

        response = requests.post(api_url, json={"order_id": str(order_id)}, timeout=8)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Delivery API returned non-object JSON")
        delivery = {
            "order_id": str(data.get("order_id") or order_id),
            "partner": str(data.get("partner") or "Dunzo"),
            "status": str(data.get("status") or "assigned"),
            "eta": str(data.get("eta") or "30 mins"),
        }
        with _LOCK:
            _DELIVERIES[delivery["order_id"]] = delivery
        log_event("delivery_assigned", delivery)
        return dict(delivery)
    except Exception:
        return assign_delivery(order_id)


def assign_delivery_safe(order_id: str | int) -> dict[str, str]:
    try:
        log_event("delivery_api_called", {"enabled": is_delivery_enabled(), "order_id": str(order_id)})
        if is_delivery_enabled():
            return assign_delivery_real(order_id)
        return assign_delivery(order_id)
    except Exception:
        return assign_delivery(order_id)


def track_delivery(order_id: str | int) -> dict[str, str]:
    try:
        key = str(order_id)
        with _LOCK:
            delivery = _DELIVERIES.get(key)
            if delivery is None:
                delivery = {"order_id": key, "partner": "Dunzo", "status": "out_for_delivery", "eta": "30 mins"}
                _DELIVERIES[key] = delivery
        if delivery.get("status") == "delivered":
            log_event("delivery_completed", {"order_id": key, "partner": delivery.get("partner", "")})
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "status": "out_for_delivery"}


def update_delivery_status(order_id: str | int, status: str) -> dict[str, str]:
    try:
        key = str(order_id)
        clean_status = str(status or "out_for_delivery").strip().lower()
        if clean_status not in {"assigned", "out_for_delivery", "delivered"}:
            clean_status = "out_for_delivery"
        with _LOCK:
            delivery = _DELIVERIES.setdefault(
                key,
                {"order_id": key, "partner": "Dunzo", "status": "assigned", "eta": "30 mins"},
            )
            delivery["status"] = clean_status
        if clean_status == "delivered":
            log_event("delivery_completed", {"order_id": key, "partner": delivery.get("partner", "")})
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "status": "out_for_delivery"}


def get_delivery_statuses() -> list[dict[str, str]]:
    try:
        with _LOCK:
            return [dict(item) for item in _DELIVERIES.values()]
    except Exception:
        return []
