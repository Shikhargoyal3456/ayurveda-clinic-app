from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.database import commit_with_retry, get_db
from app.security import sanitize_text, validate_password_complexity
from models.user import DeliveryProfile, DoctorProfile, LabProfile, PatientProfile, PharmacyProfile, User, UserProfile, UserRole, VehicleType
from services.profile_service import clear_active_profile_session, profile_avatar_for_relationship


PORTAL_ROLE_TO_SLUG: dict[str, str] = {
    UserRole.patient.value: "patient",
    UserRole.doctor.value: "doctor",
    UserRole.pharmacy_owner.value: "pharmacy",
    UserRole.lab_owner.value: "lab",
    UserRole.delivery_partner.value: "partner",
    UserRole.admin.value: "admin",
}

PORTAL_SLUG_TO_ROLE: dict[str, str] = {
    "patient": UserRole.patient.value,
    "doctor": UserRole.doctor.value,
    "pharmacy": UserRole.pharmacy_owner.value,
    "lab": UserRole.lab_owner.value,
    "partner": UserRole.delivery_partner.value,
    "admin": UserRole.admin.value,
}

PORTAL_DASHBOARD_PATHS: dict[str, str] = {
    UserRole.patient.value: "/",
    UserRole.doctor.value: "/portal/doctor",
    UserRole.pharmacy_owner.value: "/portal/pharmacy",
    UserRole.lab_owner.value: "/portal/lab",
    UserRole.delivery_partner.value: "/portal/partner",
    UserRole.admin.value: "/admin",
}

UPLOAD_ROOT = Path(__import__("os").getenv("TEST_UPLOADS_DIR", str(settings.base_dir / "temp" / "portal-uploads"))).resolve()
SESSION_TIMEOUT_MINUTES = max(5, int(__import__("os").getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30") or "30"))
OTP_TTL_MINUTES = 10
TOKEN_SERIALIZER = URLSafeTimedSerializer(settings.secret_key, salt="portal-auth")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_identifier(value: str) -> str:
    cleaned = sanitize_text(value.strip(), max_length=255)
    return cleaned.lower()


def normalize_phone(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())
    return digits[-10:]


def role_to_slug(role: str) -> str:
    return PORTAL_ROLE_TO_SLUG.get(role, "patient")


def slug_to_role(slug: str) -> str:
    return PORTAL_SLUG_TO_ROLE.get(slug, slug)


def dashboard_path_for_role(role: str) -> str:
    return PORTAL_DASHBOARD_PATHS.get(role, "/patient")


def serializer_dumps(payload: dict[str, Any]) -> str:
    return TOKEN_SERIALIZER.dumps(payload)


def serializer_loads(token: str, max_age_seconds: int) -> dict[str, Any]:
    return TOKEN_SERIALIZER.loads(token, max_age=max_age_seconds)


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp_hash(otp: str, digest: str | None) -> bool:
    if not otp or not digest:
        return False
    return hmac.compare_digest(hash_otp(otp), digest)


def create_portal_session(request, user: User, remember_me: bool = False) -> None:
    now = utc_now()
    timeout_minutes = 60 * 24 * 30 if remember_me else SESSION_TIMEOUT_MINUTES
    request.session["portal_user_id"] = user.id
    request.session["portal_user_email"] = user.email
    request.session["portal_user_name"] = user.full_name
    request.session["portal_user_role"] = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    request.session["portal_role"] = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    request.session["portal_session_version"] = int(user.session_version or 1)
    request.session["portal_session_started_at"] = now.isoformat()
    request.session["portal_last_seen_at"] = now.isoformat()
    request.session["portal_expires_at"] = (now + timedelta(minutes=timeout_minutes)).isoformat()


def clear_portal_session(request) -> None:
    for key in [
        "portal_user_id",
        "portal_user_email",
        "portal_user_name",
        "portal_user_role",
        "portal_role",
        "portal_session_version",
        "portal_session_started_at",
        "portal_last_seen_at",
        "portal_expires_at",
    ]:
        request.session.pop(key, None)
    clear_active_profile_session(request)


def portal_session_timed_out(request) -> bool:
    expires_at = request.session.get("portal_expires_at")
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(str(expires_at))
    except ValueError:
        return True
    return utc_now() >= expiry


def refresh_portal_session(request) -> None:
    if "portal_user_id" not in request.session:
        return
    now = utc_now()
    request.session["portal_last_seen_at"] = now.isoformat()
    request.session["portal_expires_at"] = (now + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()


def get_portal_user(request, db: Session) -> User | None:
    user_id = request.session.get("portal_user_id")
    if not user_id or portal_session_timed_out(request):
        clear_portal_session(request)
        return None
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        clear_portal_session(request)
        return None
    session_version = int(request.session.get("portal_session_version", 0) or 0)
    if session_version != int(user.session_version or 1):
        clear_portal_session(request)
        return None
    refresh_portal_session(request)
    return user


def require_portal_roles(*allowed_roles: str):
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        user = get_portal_user(request, db)
        if user is None:
            first_role = allowed_roles[0] if allowed_roles else UserRole.patient.value
            slug = role_to_slug(first_role)
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": f"/auth/login/{slug}"},
            )
        current_role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
        if allowed_roles and current_role not in set(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": dashboard_path_for_role(current_role)},
            )
        return user

    return dependency


def validate_portal_password(password: str) -> list[str]:
    return validate_password_complexity(password)


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    role: str,
    documents: dict[str, str | None],
    profile_data: dict[str, Any],
) -> User:
    user = User(
        email=normalize_identifier(email),
        phone=normalize_phone(phone),
        password_hash=hash_password(password),
        full_name=sanitize_text(full_name, max_length=255),
        role=UserRole(role),
        is_verified=role == UserRole.patient.value,
        verification_document_path=documents.get("verification_document_path"),
        professional_document_path=documents.get("professional_document_path"),
    )
    db.add(user)
    db.flush()

    if role == UserRole.patient.value:
        db.add(
            PatientProfile(
                user_id=user.id,
                date_of_birth=profile_data.get("date_of_birth"),
                gender=profile_data.get("gender"),
                blood_group=profile_data.get("blood_group"),
                emergency_contact_name=profile_data.get("emergency_contact_name"),
                emergency_contact_phone=profile_data.get("emergency_contact_phone"),
                medical_conditions=profile_data.get("medical_conditions"),
                allergies=profile_data.get("allergies"),
            )
        )
        db.add(
            UserProfile(
                user_id=user.id,
                profile_name=sanitize_text(full_name, max_length=100) or "Myself",
                profile_avatar=profile_avatar_for_relationship("self"),
                relationship="Self",
                date_of_birth=profile_data.get("date_of_birth"),
                gender=profile_data.get("gender"),
                blood_group=profile_data.get("blood_group"),
                medical_conditions=profile_data.get("medical_conditions"),
                allergies=profile_data.get("allergies"),
                is_primary=True,
                is_active=True,
            )
        )
    elif role == UserRole.doctor.value:
        db.add(
            DoctorProfile(
                user_id=user.id,
                specialization=profile_data.get("specialization"),
                qualification=profile_data.get("qualification"),
                registration_number=profile_data.get("registration_number"),
                experience_years=profile_data.get("experience_years"),
                consultation_fee=profile_data.get("consultation_fee"),
                available_days=profile_data.get("available_days"),
                about=profile_data.get("about"),
            )
        )
    elif role == UserRole.pharmacy_owner.value:
        db.add(
            PharmacyProfile(
                user_id=user.id,
                pharmacy_name=profile_data.get("pharmacy_name"),
                gst_number=profile_data.get("gst_number"),
                license_number=profile_data.get("license_number"),
                address=profile_data.get("address"),
                latitude=profile_data.get("latitude"),
                longitude=profile_data.get("longitude"),
                delivery_radius_km=profile_data.get("delivery_radius_km") or 5,
                minimum_order_amount=profile_data.get("minimum_order_amount"),
            )
        )
    elif role == UserRole.lab_owner.value:
        db.add(
            LabProfile(
                user_id=user.id,
                lab_name=profile_data.get("lab_name"),
                accreditation_number=profile_data.get("accreditation_number"),
                address=profile_data.get("address"),
                latitude=profile_data.get("latitude"),
                longitude=profile_data.get("longitude"),
                is_home_collection_available=bool(profile_data.get("is_home_collection_available", False)),
            )
        )
    elif role == UserRole.delivery_partner.value:
        vehicle_type = profile_data.get("vehicle_type") or VehicleType.bike.value
        db.add(
            DeliveryProfile(
                user_id=user.id,
                vehicle_type=VehicleType(vehicle_type),
                vehicle_number=profile_data.get("vehicle_number"),
                dl_number=profile_data.get("dl_number"),
                current_latitude=profile_data.get("current_latitude"),
                current_longitude=profile_data.get("current_longitude"),
            )
        )

    commit_with_retry(db)
    db.refresh(user)
    return user


def verify_user_password(user: User, password: str) -> bool:
    return verify_password(password, user.password_hash)


def set_user_otp(db: Session, user: User, otp: str, purpose: str = "login") -> None:
    user.otp_code_hash = hash_otp(otp)
    user.otp_expires_at = utc_now() + timedelta(minutes=OTP_TTL_MINUTES)
    user.otp_purpose = purpose
    commit_with_retry(db)


def consume_user_otp(db: Session, user: User) -> None:
    user.otp_code_hash = None
    user.otp_expires_at = None
    user.otp_purpose = None
    commit_with_retry(db)


def otp_is_valid(user: User, otp: str, purpose: str = "login") -> bool:
    if user.otp_purpose != purpose or not user.otp_expires_at:
        return False
    expires_at = user.otp_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utc_now() > expires_at:
        return False
    return verify_otp_hash(otp, user.otp_code_hash)


def save_upload(upload, category: str) -> str | None:
    if upload is None or not getattr(upload, "filename", ""):
        return None
    safe_suffix = Path(str(upload.filename)).suffix.lower()
    if safe_suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        return None
    category_dir = UPLOAD_ROOT / category
    category_dir.mkdir(parents=True, exist_ok=True)
    destination = category_dir / f"{secrets.token_hex(16)}{safe_suffix}"
    with destination.open("wb") as handle:
        contents = upload.file.read()
        handle.write(contents[:5_000_000])
    return str(destination)


def build_verification_email(user: User, verify_url: str) -> tuple[str, str]:
    subject = "Verify your Kash AI portal account"
    body = (
        f"<h2>Welcome, {user.full_name}</h2>"
        f"<p>Please verify your {role_to_slug(user.role.value)} portal account to continue.</p>"
        f"<p><a href=\"{verify_url}\">Verify email address</a></p>"
        "<p>This link expires in 24 hours.</p>"
    )
    return subject, body


def build_reset_email(user: User, reset_url: str) -> tuple[str, str]:
    subject = "Reset your Kash AI portal password"
    body = (
        f"<h2>Password reset requested</h2>"
        f"<p>Hello {user.full_name}, use the secure link below to reset your password.</p>"
        f"<p><a href=\"{reset_url}\">Reset password</a></p>"
        "<p>This link expires in 30 minutes. If you did not request this, you can ignore this email.</p>"
    )
    return subject, body


def user_public_context(user: User) -> dict[str, str]:
    role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    initials = "".join(part[:1] for part in user.full_name.split()[:2]).upper() or "KA"
    return {
        "user_name": user.full_name,
        "user_role": role.replace("_", " ").title(),
        "avatar_label": initials[:2],
        "portal_role": role,
        "portal_slug": role_to_slug(role),
    }


def parse_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
