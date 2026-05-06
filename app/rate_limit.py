from __future__ import annotations

from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


_default_requests = max(1, getattr(settings, "rate_limit_requests", 100))
_default_period = max(1, getattr(settings, "rate_limit_period", 60))
_rate_limit_enabled = getattr(settings, "rate_limit_enabled", True)


def _format_default_limit(requests: int, period_seconds: int) -> str:
    if period_seconds == 60:
        return f"{requests}/minute"
    if period_seconds == 3600:
        return f"{requests}/hour"
    if period_seconds == 86400:
        return f"{requests}/day"
    return f"{requests}/minute"


DEFAULT_LIMIT = _format_default_limit(_default_requests, _default_period) if _rate_limit_enabled else "100/minute"


def _key_func(request: Any) -> str:
    forwarded = getattr(request, "headers", {}).get("x-forwarded-for") if getattr(request, "headers", None) else None
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func, default_limits=[DEFAULT_LIMIT])

RATE_LIMITS = {
    "login": "5/minute",
    "register": "3/minute",
    "checkout": "10/minute",
    "search": "30/minute",
    "upload": "20/minute",
    "api": "100/minute",
}


def rate_limit_by_role(role: str) -> str:
    role = str(role or "").strip().lower()
    if role == "admin":
        return "500/minute"
    if role == "delivery_partner":
        return "300/minute"
    if role == "pharmacy_owner":
        return "200/minute"
    if role == "patient":
        return "100/minute"
    return "50/minute"
