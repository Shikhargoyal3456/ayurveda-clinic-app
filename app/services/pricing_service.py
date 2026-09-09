from __future__ import annotations

from collections import Counter
from typing import Any

from app.analytics import log_event
from services.analytics_service import load_events
from services.feature_flags import is_pricing_enabled


def _demand_counts() -> Counter[str]:
    counts: Counter[str] = Counter()
    try:
        for event in load_events():
            if str(event.get("event_name") or "") not in {"medicine_added_to_cart", "order_created"}:
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            medicine = str(data.get("medicine_name") or data.get("medicine") or "").strip()
            if medicine:
                counts[medicine] += 1
    except Exception:
        return Counter()
    return counts


def get_price(medicine_name: str, base_price: int | float) -> int:
    try:
        price = float(base_price or 0)
        if price <= 0 or not is_pricing_enabled():
            return int(round(price))
        demand = _demand_counts().get(str(medicine_name or "").strip(), 0)
        demand_factor = 1.0
        if demand >= 10:
            demand_factor = 1.1
        elif demand <= 1:
            demand_factor = 0.95
        adjusted = max(int(round(price * demand_factor)), 0)
        if adjusted != int(round(price)):
            log_event(
                "pricing_adjusted",
                {"medicine_name": medicine_name, "base_price": price, "adjusted_price": adjusted, "demand": demand},
            )
        return adjusted
    except Exception:
        try:
            return int(round(float(base_price or 0)))
        except Exception:
            return 0


def get_pricing_preview() -> list[dict[str, Any]]:
    try:
        demand = _demand_counts()
        medicines = sorted(demand)[:10] or ["Paracetamol", "Ibuprofen", "Ashwagandha"]
        return [
            {"medicine": medicine, "base_price": 100, "price": get_price(medicine, 100), "demand": demand.get(medicine, 0)}
            for medicine in medicines
        ]
    except Exception:
        return []
