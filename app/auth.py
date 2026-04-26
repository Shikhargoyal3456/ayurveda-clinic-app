from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from base64 import b64decode
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.database import commit_with_retry, get_db
from app.models import Doctor
from app.security import (
    clear_failed_login,
    compare_refresh_token,
    hash_refresh_token,
    invalidate_current_session,
    is_bruteforce_blocked,
    issue_session_tokens,
    record_failed_login,
    refresh_session_if_needed,
    sanitize_text,
    session_timed_out,
)

PASSWORD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_LAST_SWEEP_AT = 0.0


def _apply_rate_limit(key: str, limit: int, window_seconds: int) -> int | None:
    global _RATE_LIMIT_LAST_SWEEP_AT
    now = time.time()
    with _RATE_LIMIT_LOCK:
        if now - _RATE_LIMIT_LAST_SWEEP_AT > max(30, window_seconds):
            stale_keys = [
                bucket_key
                for bucket_key, bucket_entries in _RATE_LIMIT_BUCKETS.items()
                if not bucket_entries or now - bucket_entries[-1] > window_seconds
            ]
            for stale_key in stale_keys:
                _RATE_LIMIT_BUCKETS.pop(stale_key, None)
            _RATE_LIMIT_LAST_SWEEP_AT = now
        entries = _RATE_LIMIT_BUCKETS[key]
        while entries and now - entries[0] > window_seconds:
            entries.popleft()
        if len(entries) >= limit:
            retry_after_seconds = max(1, int(window_seconds - (now - entries[0])))
            return retry_after_seconds
        entries.append(now)
        return None


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def _verify_legacy_password(password: str, password_hash: str) -> bool:
    try:
        salt_b64, digest_b64 = password_hash.split("$", 1)
    except ValueError:
        return False
    salt = b64decode(salt_b64.encode())
    expected = b64decode(digest_b64.encode())
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("$pbkdf2-sha256$"):
        return PASSWORD_CONTEXT.verify(password, password_hash)
    return _verify_legacy_password(password, password_hash)


def needs_password_rehash(password_hash: str) -> bool:
    return not password_hash.startswith("$pbkdf2-sha256$")


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["_csrf_token"] = token
    return token


async def verify_csrf(request: Request) -> None:
    expected = ensure_csrf_token(request)
    submitted = request.headers.get("X-CSRF-Token", "").strip()

    if not submitted:
        content_type = request.headers.get("content-type", "").lower()
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            submitted = str(form.get("csrf_token", "")).strip()

    if not submitted or not hmac.compare_digest(expected, submitted):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")


def rate_limit_dependency(bucket: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client_ip}"
        retry_after_seconds = _apply_rate_limit(key, limit=limit, window_seconds=window_seconds)
        if retry_after_seconds is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait and try again.",
                headers={"Retry-After": str(retry_after_seconds)},
            )

    return dependency


def get_current_doctor(request: Request, db: Session = Depends(get_db)) -> Doctor:
    doctor_id = request.session.get("doctor_id")
    if not doctor_id:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        invalidate_current_session(request)
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    if session_timed_out(request):
        invalidate_current_session(request)
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    if int(request.session.get("session_version", -1)) != int(doctor.session_version):
        invalidate_current_session(request)
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    refresh_token = str(request.session.get("refresh_token", ""))
    if doctor.refresh_token_hash and not compare_refresh_token(refresh_token, doctor.refresh_token_hash):
        invalidate_current_session(request)
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    refresh_session_if_needed(request)
    return doctor


def set_flash(request: Request, message: str, category: str = "info") -> None:
    request.session["_flash"] = {"message": message, "category": category}


def pop_flash(request: Request) -> dict[str, str] | None:
    return request.session.pop("_flash", None)


def initialize_login_session(request: Request, doctor: Doctor, db: Session) -> None:
    request.session.clear()
    request.session["_csrf_token"] = ensure_csrf_token(request)
    issue_session_tokens(request, doctor.id, doctor.session_version)
    doctor.last_login_at = doctor.last_login_at or None
    doctor.refresh_token_hash = hash_refresh_token(str(request.session.get("refresh_token", "")))
    doctor.failed_login_attempts = 0
    doctor.locked_until = None
    doctor.last_login_at = doctor.last_login_at or None
    commit_with_retry(db)


def mark_login_success(doctor: Doctor, request: Request, db: Session) -> None:
    clear_failed_login(doctor.username)
    doctor.failed_login_attempts = 0
    doctor.locked_until = None
    doctor.last_login_at = doctor.last_login_at or request.state.request_started_at
    doctor.refresh_token_hash = hash_refresh_token(str(request.session.get("refresh_token", "")))
    commit_with_retry(db)


def register_login_failure(doctor: Doctor | None, identifier: str, request: Request, db: Session | None = None) -> str:
    record_failed_login(identifier)
    failures = 1
    if doctor is not None:
        doctor.failed_login_attempts = int(doctor.failed_login_attempts or 0) + 1
        failures = doctor.failed_login_attempts
        if failures >= 8:
            doctor.locked_until = request.state.request_started_at + timedelta(minutes=15)
        if db is not None:
            commit_with_retry(db)
    if is_bruteforce_blocked(identifier):
        return "Too many failed attempts. Please wait before trying again."
    return "Invalid username or password."


def normalized_username(username: str) -> str:
    return sanitize_text(username.lower(), max_length=120)
