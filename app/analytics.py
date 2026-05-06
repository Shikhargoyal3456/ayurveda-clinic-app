from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from app.config import settings


_analytics_lock = Lock()
_event_lock = Lock()
_error_lock = Lock()
_analytics_cache_lock = Lock()
_analytics_cache: dict[str, Any] = {
    "signature": None,
    "payload": None,
}
ORDER_FUNNEL_EVENTS = ("search_performed", "medicine_added_to_cart", "checkout_started", "payment_success")
DIRECT_ORDER_EVENTS = {
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
    "error_logged",
    "patient_consent_given",
    "order_medicines_page_viewed",
    "prescription_order_initiated",
    "otc_order_initiated",
}


def _analytics_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.analytics_log_path


def _event_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.logs_dir / "events.jsonl"


def _error_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.logs_dir / "errors.jsonl"


def log_event(event_name: str, data: dict[str, Any]) -> None:
    try:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_name": event_name,
            "data": data,
        }
        with _event_lock:
            with _event_path().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def log_error(error_type: str, message: str, context: dict[str, Any]) -> None:
    try:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "message": message,
            "context": context,
        }
        with _error_lock:
            with _error_path().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


def log_route_errors(error_type: str, route: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if getattr(func, "__code__", None) and func.__code__.co_flags & 0x80:
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    log_error(error_type, str(exc), {"route": route})
                    raise

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                log_error(error_type, str(exc), {"route": route})
                raise

        return wrapper

    return decorator


def track_event(event: str, **details: Any) -> None:
    try:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        }
        with _analytics_lock:
            with _analytics_path().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        log_event(event, details)
    except Exception:
        pass


def track_error_event(error_type: str, route: str, message: str, **details: Any) -> None:
    log_error(error_type, message, {"route": route, **details})
    track_event(
        "error_logged",
        error_type=error_type,
        route=route,
        message=message,
        **details,
    )


def aggregate_daily_statistics() -> dict[str, Any]:
    path = _analytics_path()
    if not path.exists():
        return {"days": {}, "totals": {}, "funnel": {"search": 0, "cart": 0, "checkout": 0, "payment": 0}}

    stat = path.stat()
    signature = (str(path), stat.st_mtime_ns, stat.st_size)
    with _analytics_cache_lock:
        if _analytics_cache.get("signature") == signature and isinstance(_analytics_cache.get("payload"), dict):
            return dict(_analytics_cache["payload"])

    daily: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        item = json.loads(raw_line)
        timestamp = str(item.get("timestamp", ""))
        day = timestamp[:10] if len(timestamp) >= 10 else "unknown"
        event = str(item.get("event", "unknown"))
        daily.setdefault(day, Counter())[event] += 1
        totals[event] += 1
    payload = {
        "days": {day: dict(counter) for day, counter in sorted(daily.items())},
        "totals": dict(totals),
        "funnel": {
            "search": totals["search_performed"],
            "cart": totals["medicine_added_to_cart"],
            "checkout": totals["checkout_started"],
            "payment": totals["payment_success"],
        },
    }
    with _analytics_cache_lock:
        _analytics_cache["signature"] = signature
        _analytics_cache["payload"] = payload
    return dict(payload)
