from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock
from typing import Any, Callable

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings

try:
    import bleach  # type: ignore
except Exception:  # pragma: no cover
    bleach = None


logger = logging.getLogger(__name__)
_security_lock = Lock()
_active_sessions: dict[str, dict[str, Any]] = {}
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_text(value: str, max_length: int | None = None) -> str:
    cleaned = html.escape(value.strip(), quote=False)
    if max_length is not None:
        cleaned = cleaned[:max_length]
    return cleaned


class Sanitizer:
    @staticmethod
    def sanitize_html(text: str) -> str:
        raw = str(text or "").strip()
        if bleach is None:
            return sanitize_text(raw)
        return bleach.clean(raw, tags=["b", "i", "u", "p", "br"], attributes={}, strip=True)

    @staticmethod
    def sanitize_phone(phone: str) -> str:
        digits = "".join(char for char in str(phone or "") if char.isdigit())
        if len(digits) != 10:
            raise ValueError("Invalid phone number")
        return digits

    @staticmethod
    def sanitize_pincode(pincode: str) -> str:
        digits = "".join(char for char in str(pincode or "") if char.isdigit())
        if len(digits) != 6:
            raise ValueError("Invalid pincode")
        return digits

    @staticmethod
    def sanitize_email(email: str) -> str:
        cleaned = str(email or "").strip().lower()
        if not _EMAIL_REGEX.match(cleaned):
            raise ValueError("Invalid email address")
        return cleaned


def validate_password_complexity(password: str) -> list[str]:
    issues: list[str] = []
    if len(password) < 10:
        issues.append("Password must be at least 10 characters long.")
    if not any(char.isupper() for char in password):
        issues.append("Password must include at least one uppercase letter.")
    if not any(char.islower() for char in password):
        issues.append("Password must include at least one lowercase letter.")
    if not any(char.isdigit() for char in password):
        issues.append("Password must include at least one number.")
    if not any(not char.isalnum() for char in password):
        issues.append("Password must include at least one special character.")
    return issues


def record_failed_login(identifier: str) -> int:
    now = time.time()
    bucket = _login_attempts[identifier]
    while bucket and now - bucket[0] > 900:
        bucket.popleft()
    bucket.append(now)
    return len(bucket)


def clear_failed_login(identifier: str) -> None:
    _login_attempts.pop(identifier, None)


def is_bruteforce_blocked(identifier: str, limit: int = 8, window_seconds: int = 900) -> bool:
    now = time.time()
    bucket = _login_attempts[identifier]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    return len(bucket) >= limit


def failed_login_retry_after_seconds(
    identifier: str,
    *,
    base_delay_seconds: int = 2,
    max_delay_seconds: int = 300,
    window_seconds: int = 900,
) -> int:
    now = time.time()
    bucket = _login_attempts[identifier]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    attempts = len(bucket)
    if attempts <= 1:
        return 0
    delay = min(max_delay_seconds, base_delay_seconds * (2 ** max(0, attempts - 2)))
    elapsed_since_last_attempt = now - bucket[-1]
    remaining = int(delay - elapsed_since_last_attempt)
    return max(0, remaining)


def _session_timeout_seconds() -> int:
    return settings.session_idle_timeout_minutes * 60


def issue_session_tokens(request: Request, doctor_id: int, session_version: int) -> None:
    now = utc_now()
    refresh_token = secrets.token_urlsafe(32)
    request.session["doctor_id"] = doctor_id
    request.session["session_version"] = session_version
    request.session["session_started_at"] = now.isoformat()
    request.session["last_seen_at"] = now.isoformat()
    request.session["session_expires_at"] = (now + timedelta(seconds=_session_timeout_seconds())).isoformat()
    request.session["refresh_token"] = refresh_token
    with _security_lock:
        _active_sessions[f"{doctor_id}:{refresh_token}"] = {
            "doctor_id": doctor_id,
            "issued_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
        }


def session_timed_out(request: Request) -> bool:
    expires_at = request.session.get("session_expires_at")
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return utc_now() >= expiry


def refresh_session_if_needed(request: Request) -> None:
    if "doctor_id" not in request.session:
        return
    now = utc_now()
    request.session["last_seen_at"] = now.isoformat()
    request.session["session_expires_at"] = (now + timedelta(seconds=_session_timeout_seconds())).isoformat()
    refresh_token = request.session.get("refresh_token")
    if refresh_token:
        with _security_lock:
            session_key = f"{request.session.get('doctor_id')}:{refresh_token}"
            if session_key in _active_sessions:
                _active_sessions[session_key]["last_seen_at"] = now.isoformat()


def invalidate_current_session(request: Request) -> None:
    refresh_token = request.session.get("refresh_token")
    doctor_id = request.session.get("doctor_id")
    if refresh_token and doctor_id:
        with _security_lock:
            _active_sessions.pop(f"{doctor_id}:{refresh_token}", None)
    request.session.clear()


def invalidate_all_sessions_for_doctor(doctor_id: int) -> None:
    with _security_lock:
        keys = [key for key, value in _active_sessions.items() if value.get("doctor_id") == doctor_id]
        for key in keys:
            _active_sessions.pop(key, None)


def active_session_count() -> int:
    with _security_lock:
        return len(_active_sessions)


def active_sessions_snapshot() -> list[dict[str, Any]]:
    with _security_lock:
        return [dict(session_key=key, **value) for key, value in _active_sessions.items()]


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compare_refresh_token(token: str, token_hash: str | None) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_refresh_token(token), token_hash)


def audit_logged(event_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("security_event=%s context=%s", event_name, json.dumps({"args": len(args), "kwargs": list(kwargs)}))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def ensure_https_request(request: Request) -> None:
    if not settings.https_redirect_enabled:
        return
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if forwarded_proto != "https" and settings.is_production:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HTTPS is required.")


class SecureModels:
    class MedicineInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        name: str = Field(min_length=2, max_length=200)
        price: float
        stock: int

        @field_validator("name")
        @classmethod
        def validate_name(cls, value: str) -> str:
            return Sanitizer.sanitize_html(value)

        @field_validator("price")
        @classmethod
        def validate_price(cls, value: float) -> float:
            if value <= 0:
                raise ValueError("Price must be positive")
            if value > 100000:
                raise ValueError("Price too high")
            return round(float(value), 2)

        @field_validator("stock")
        @classmethod
        def validate_stock(cls, value: int) -> int:
            if value < 0:
                raise ValueError("Stock cannot be negative")
            if value > 100000:
                raise ValueError("Stock too high")
            return int(value)

    class OrderInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        items: list[dict[str, Any]]
        address: str = Field(min_length=5, max_length=500)
        payment_method: str = Field(min_length=2, max_length=40)

        @field_validator("address")
        @classmethod
        def validate_address(cls, value: str) -> str:
            return Sanitizer.sanitize_html(value)

    class ContactInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True)

        email: str
        phone: str
        pincode: str | None = None

        @field_validator("email")
        @classmethod
        def validate_email(cls, value: str) -> str:
            return Sanitizer.sanitize_email(value)

        @field_validator("phone")
        @classmethod
        def validate_phone(cls, value: str) -> str:
            return Sanitizer.sanitize_phone(value)

        @field_validator("pincode")
        @classmethod
        def validate_pincode(cls, value: str | None) -> str | None:
            if value in {None, ""}:
                return None
            return Sanitizer.sanitize_pincode(value)
