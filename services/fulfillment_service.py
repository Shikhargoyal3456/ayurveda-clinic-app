from __future__ import annotations

from threading import Lock
from typing import Any

from app.analytics import log_event


_STATUSES = {"placed", "packed", "shipped", "delivered"}
_ORDERS: dict[str, str] = {}
_LOCK = Lock()


def track_order(order_id: str | int) -> dict[str, str]:
    try:
        key = str(order_id)
        with _LOCK:
            status = _ORDERS.setdefault(key, "placed")
        return {"order_id": key, "status": status}
    except Exception:
        return {"order_id": str(order_id), "status": "placed"}


def update_status(order_id: str | int, status: str) -> dict[str, str]:
    try:
        key = str(order_id)
        clean_status = str(status or "").strip().lower()
        if clean_status not in _STATUSES:
            clean_status = "placed"
        with _LOCK:
            _ORDERS[key] = clean_status
        if clean_status == "delivered":
            log_event("order_fulfilled", {"order_id": key, "status": clean_status})
        return {"order_id": key, "status": clean_status}
    except Exception:
        return {"order_id": str(order_id), "status": "placed"}


def get_fulfillment_statuses() -> list[dict[str, str]]:
    try:
        with _LOCK:
            return [{"order_id": order_id, "status": status} for order_id, status in _ORDERS.items()]
    except Exception:
        return []
