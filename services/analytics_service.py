from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

from app.config import settings


EVENT_NAMES = (
    "search_performed",
    "ai_used",
    "ai_add_all_clicked",
    "medicine_added_to_cart",
    "cart_opened",
    "checkout_started",
    "payment_attempted",
    "payment_success",
    "payment_failed",
    "order_created",
)
MAX_LOG_LINES = 5000
SPECIALTIES = ("ayurveda", "modern_medicine", "homeopathy", "dental", "physiotherapy", "unknown")
_JSONL_CACHE: dict[tuple[str, int], tuple[tuple[str, int, int], list[dict[str, Any]]]] = {}


def _read_jsonl(path: Path, limit: int = MAX_LOG_LINES) -> list[dict[str, Any]]:
    if path.exists():
        stat = path.stat()
        signature = (str(path), stat.st_mtime_ns, stat.st_size)
        cached = _JSONL_CACHE.get((str(path), limit))
        if cached and cached[0] == signature:
            return list(cached[1])
    items: list[dict[str, Any]] = []
    try:
        if not path.exists():
            return items
        with path.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=limit)
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    except Exception:
        return []
    if path.exists():
        stat = path.stat()
        _JSONL_CACHE[(str(path), limit)] = ((str(path), stat.st_mtime_ns, stat.st_size), items)
    return items


def load_events() -> list[dict[str, Any]]:
    return _read_jsonl(settings.logs_dir / "events.jsonl")


def load_errors() -> list[dict[str, Any]]:
    return _read_jsonl(settings.logs_dir / "errors.jsonl")


def cleanup_logs(max_lines: int = 10000) -> None:
    for path in (settings.logs_dir / "events.jsonl", settings.logs_dir / "errors.jsonl"):
        try:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as handle:
                lines = deque(handle, maxlen=max_lines)
            with path.open("w", encoding="utf-8") as handle:
                handle.writelines(lines)
        except Exception:
            continue


def _safe_divide(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def get_funnel_metrics() -> dict[str, int]:
    counts = Counter(str(item.get("event_name", "")) for item in load_events())
    return {
        "search": counts["search_performed"],
        "ai_used": counts["ai_used"],
        "ai_add_all_clicked": counts["ai_add_all_clicked"],
        "add_to_cart": counts["medicine_added_to_cart"],
        "cart_opened": counts["cart_opened"],
        "checkout_started": counts["checkout_started"],
        "payment_attempted": counts["payment_attempted"],
        "payment_success": counts["payment_success"],
        "payment_failed": counts["payment_failed"],
        "order_created": counts["order_created"],
    }


def get_conversion_rates() -> dict[str, float]:
    counts = get_funnel_metrics()
    return {
        "search_to_ai": _safe_divide(counts["ai_used"], counts["search"]),
        "ai_to_cart": _safe_divide(counts["add_to_cart"], counts["ai_used"]),
        "cart_to_checkout": _safe_divide(counts["checkout_started"], counts["add_to_cart"]),
        "checkout_to_payment": _safe_divide(counts["payment_success"], counts["checkout_started"]),
    }


def get_revenue_metrics() -> dict[str, int]:
    total_orders = 0
    successful_payments = 0
    estimated_revenue = 0.0
    for item in load_events():
        event_name = str(item.get("event_name") or "")
        data = _event_data(item)
        if event_name == "order_created":
            total_orders += 1
        if event_name == "payment_success":
            successful_payments += 1
            try:
                estimated_revenue += float(data.get("total") or data.get("amount") or 0)
            except (TypeError, ValueError):
                continue
    return {
        "total_orders": total_orders,
        "successful_payments": successful_payments,
        "estimated_revenue": int(round(estimated_revenue)),
    }


def _event_data(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data")
    return data if isinstance(data, dict) else {}


def _top_items(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [{key: name, "count": count} for name, count in counter.most_common(5)]


def _event_system(data: dict[str, Any]) -> str:
    system = str(data.get("system") or "unknown").strip().lower()
    return system if system in SPECIALTIES else "unknown"


def _empty_specialty_metrics() -> dict[str, int | float]:
    return {
        "ai_uses": 0,
        "ai_to_cart": 0,
        "ai_to_order": 0,
        "conversion_rate": 0.0,
        "contribution_rate": 0.0,
    }


def get_ai_performance_metrics() -> dict[str, Any]:
    total_ai_uses = 0
    ai_to_cart = 0
    ai_to_order = 0
    by_specialty = {specialty: _empty_specialty_metrics() for specialty in SPECIALTIES}
    medicines: Counter[str] = Counter()
    diseases: Counter[str] = Counter()

    for item in load_events():
        event_name = str(item.get("event_name") or "")
        if event_name not in {"ai_used", "ai_add_all_clicked", "medicine_added_to_cart", "order_created"}:
            continue
        data = _event_data(item)
        source = str(data.get("source") or "").lower()
        system = _event_system(data)
        specialty_metrics = by_specialty[system]

        if event_name == "ai_used":
            total_ai_uses += 1
            specialty_metrics["ai_uses"] = int(specialty_metrics["ai_uses"]) + 1
        elif event_name == "ai_add_all_clicked":
            pass
        elif event_name == "medicine_added_to_cart" and source == "ai":
            ai_to_cart += 1
            specialty_metrics["ai_to_cart"] = int(specialty_metrics["ai_to_cart"]) + 1
        elif event_name == "order_created" and source == "ai":
            ai_to_order += 1
            specialty_metrics["ai_to_order"] = int(specialty_metrics["ai_to_order"]) + 1

        disease = data.get("disease")
        if disease:
            diseases[str(disease)] += 1

        if event_name in {"medicine_added_to_cart", "order_created"}:
            medicine_name = data.get("medicine_name")
            if medicine_name:
                medicines[str(medicine_name)] += 1

    for metrics in by_specialty.values():
        metrics["conversion_rate"] = _safe_divide(int(metrics["ai_to_order"]), int(metrics["ai_uses"]))
        metrics["contribution_rate"] = _safe_divide(int(metrics["ai_uses"]), total_ai_uses)

    return {
        "overall": {
            "total_ai_uses": total_ai_uses,
            "ai_to_cart": ai_to_cart,
            "ai_to_order": ai_to_order,
            "ai_to_cart_rate": _safe_divide(ai_to_cart, total_ai_uses),
            "ai_to_order_rate": _safe_divide(ai_to_order, total_ai_uses),
        },
        "by_specialty": by_specialty,
        "top_medicines": _top_items(medicines, "name"),
        "top_diseases": _top_items(diseases, "disease"),
    }


def get_ai_optimization_insights() -> dict[str, Any]:
    try:
        metrics = get_ai_performance_metrics()
        overall = metrics.get("overall") if isinstance(metrics.get("overall"), dict) else {}
        by_specialty = metrics.get("by_specialty") if isinstance(metrics.get("by_specialty"), dict) else {}
        active_specialties = [
            {
                "name": str(name),
                "conversion_rate": float(values.get("conversion_rate") or 0.0),
                "contribution_rate": float(values.get("contribution_rate") or 0.0),
            }
            for name, values in by_specialty.items()
            if isinstance(values, dict) and int(values.get("ai_uses") or 0) > 0
        ]
        if not active_specialties:
            return {"best_specialty": {}, "worst_specialty": {}, "recommendations": []}

        best = max(active_specialties, key=lambda item: item["conversion_rate"])
        worst = min(active_specialties, key=lambda item: item["conversion_rate"])
        recommendations = [
            f"Promote {best['name']} recommendations more in AI flow",
            f"Review or improve {worst['name']} AI prompts",
        ]

        if float(overall.get("ai_to_order_rate") or 0.0) < 0.1:
            recommendations.append("Overall AI conversion is low. Improve recommendation quality")

        dominant = next((item for item in active_specialties if item["contribution_rate"] > 0.5), None)
        if dominant:
            recommendations.append(f"High dependency on {dominant['name']}. Consider balancing recommendations")

        return {
            "best_specialty": {"name": best["name"], "conversion_rate": best["conversion_rate"]},
            "worst_specialty": {"name": worst["name"], "conversion_rate": worst["conversion_rate"]},
            "recommendations": recommendations,
        }
    except Exception:
        return {"best_specialty": {}, "worst_specialty": {}, "recommendations": []}


def get_error_summary() -> dict[str, Any]:
    errors = load_errors()
    by_type: Counter[str] = Counter()
    by_route: Counter[str] = Counter()
    for item in errors:
        by_type[str(item.get("error_type") or "unknown")] += 1
        context = item.get("context") if isinstance(item.get("context"), dict) else {}
        route = context.get("route") if isinstance(context, dict) else None
        if route:
            by_route[str(route)] += 1
    return {
        "total_errors": len(errors),
        "errors_by_type": dict(by_type),
        "errors_by_route": dict(by_route),
    }


def get_alerts(error_threshold: int = 50) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    rates = get_conversion_rates()
    error_summary = get_error_summary()
    if rates["ai_to_cart"] < 0.2:
        alerts.append({"type": "warning", "message": "AI recommendations underperforming"})
    if rates["checkout_to_payment"] < 0.5:
        alerts.append({"type": "warning", "message": "Payment conversion issue"})
    if error_summary["total_errors"] > error_threshold:
        alerts.append({"type": "warning", "message": "High system errors"})
    return alerts
