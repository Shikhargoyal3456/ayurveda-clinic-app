from __future__ import annotations

from threading import Lock
from typing import Any

from app.analytics import log_event


_PHARMACIES: list[dict[str, Any]] = [
    {"id": "pharma_1", "name": "City Care Pharmacy", "location": "Delhi", "active": True},
    {"id": "pharma_2", "name": "HealthPlus Pharmacy", "location": "Gurgaon", "active": True},
]
_LOCK = Lock()


def get_pharmacies() -> list[dict[str, Any]]:
    try:
        with _LOCK:
            return [dict(item) for item in _PHARMACIES]
    except Exception:
        return []


def register_pharmacy(data: dict[str, Any] | None) -> dict[str, Any]:
    try:
        payload = data or {}
        name = str(payload.get("name") or "").strip()
        location = str(payload.get("location") or "").strip()
        if not name or not location:
            return {"success": False, "error": "name_and_location_required"}
        with _LOCK:
            pharmacy = {
                "id": f"pharma_{len(_PHARMACIES) + 1}",
                "name": name,
                "location": location,
                "active": True,
            }
            _PHARMACIES.append(pharmacy)
        log_event("pharmacy_registered", {"pharmacy_id": pharmacy["id"], "name": name, "location": location})
        return {"success": True, "pharmacy": dict(pharmacy)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
