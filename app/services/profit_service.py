from __future__ import annotations

from typing import Any

from app.analytics import log_event
from services.analytics_service import load_events


def _amount(data: dict[str, Any]) -> float:
    try:
        return float(data.get("total") or data.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def get_profit_metrics() -> dict[str, int | float]:
    try:
        total_revenue = 0.0
        for event in load_events():
            if str(event.get("event_name") or "") == "payment_success":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                total_revenue += _amount(data)
        estimated_cost = total_revenue * 0.7
        estimated_profit = total_revenue - estimated_cost
        margin = estimated_profit / total_revenue if total_revenue > 0 else 0.0
        result = {
            "total_revenue": int(round(total_revenue)),
            "estimated_cost": int(round(estimated_cost)),
            "estimated_profit": int(round(estimated_profit)),
            "profit_margin": round(margin, 4),
        }
        log_event("profit_calculated", result)
        return result
    except Exception:
        return {"total_revenue": 0, "estimated_cost": 0, "estimated_profit": 0, "profit_margin": 0.0}
