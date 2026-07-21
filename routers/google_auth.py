from __future__ import annotations

import logging
import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.config import settings
from app.database import commit_with_retry, get_db
from app.portal_auth import (
    create_user,
    ensure_legacy_doctor_for_portal_user,
    normalize_identifier,
    normalize_phone,
)
from app.auth import verify_csrf
from models.user import User, UserRole
from routers.auth import PORTAL_CONFIG, _complete_portal_login


logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(prefix="/auth/google", tags=["google-auth"])
oauth = OAuth()


def _google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


if _google_configured():
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _google_avatar_label(full_name: str) -> str:
    initials = "".join(part[:1] for part in full_name.split()[:2]).upper()
    return initials[:2] or "KA"


def _remember_google_signup(request: Request, userinfo: dict[str, str], preferred_role: str = "") -> None:
    request.session["google_signup"] = {
        "email": normalize_identifier(str(userinfo.get("email", "")).strip()),
        "full_name": str(userinfo.get("name", "")).strip() or "Kash AI User",
        "google_id": str(userinfo.get("sub", "")).strip(),
        "picture": str(userinfo.get("picture", "")).strip(),
        "preferred_role": preferred_role,
    }


def _clear_google_signup(request: Request) -> None:
    request.session.pop("google_signup", None)


def _google_role_context(request: Request, google_user: dict[str, str], error: str = "") -> dict[str, object]:
    preferred_role = str(google_user.get("preferred_role", "")).strip().lower()
    role_cards = []
    for slug in ("doctor", "patient"):
        config = PORTAL_CONFIG[slug]
        role_cards.append(
            {
                "slug": slug,
                "label": config["name"],
                "icon": config["icon"],
                "description": config["benefits"][0],
                "selected": preferred_role == slug,
            }
        )
    return {
        "request": request,
        "google_user": google_user,
        "role_cards": role_cards,
        "error": error,
        "csrf_token": request.state.csrf_token,
        "hide_footer": True,
        "hide_header": True,
        "user_name": google_user.get("full_name") or "Google signup",
        "user_role": "Google onboarding",
        "avatar_label": _google_avatar_label(google_user.get("full_name", "")),
    }


def _complete_google_login(request: Request, db: Session, user: User) -> RedirectResponse:
    user.is_active = True
    commit_with_retry(db)
    if user.role == UserRole.doctor:
        ensure_legacy_doctor_for_portal_user(db, user)
    track_event("google_login", role=user.role.value, user_id=user.id)
    return _complete_portal_login(request, db, user, remember_me=True, audit_name="google_login_success")


def _build_google_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    google_id: str,
    picture: str,
    role: str,
    phone: str,
) -> User:
    user = create_user(
        db,
        full_name=full_name.strip() or "Kash AI User",
        email=normalize_identifier(email),
        phone=normalize_phone(phone),
        password=secrets.token_urlsafe(32),
        role=role,
        documents={"verification_document_path": None, "professional_document_path": None},
        profile_data={
            "doctor_type": "ayurveda",
            "registration_number": None,
            "specialization": None,
            "qualification": None,
            "experience_years": None,
            "consultation_fee": None,
            "available_days": None,
            "about": None,
            "date_of_birth": None,
            "gender": None,
            "blood_group": None,
            "emergency_contact_name": None,
            "emergency_contact_phone": None,
            "medical_conditions": None,
            "allergies": None,
        },
    )
    user.google_id = google_id or None
    user.profile_picture = picture or None
    user.is_active = True
    user.is_verified = True
    commit_with_retry(db)
    db.refresh(user)
    return user


@router.get("/login")
async def google_login(request: Request, role: str | None = None):
    if not _google_configured():
        raise HTTPException(status_code=503, detail="Google login is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    preferred_role = str(role or "").strip().lower()
    request.session["google_preferred_role"] = preferred_role
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not _google_configured():
        raise HTTPException(status_code=503, detail="Google login is not configured.")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:  # pragma: no cover
        logger.exception("Google OAuth token exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="Google authentication failed.") from exc

    userinfo = token.get("userinfo") or {}
    email = normalize_identifier(str(userinfo.get("email", "")).strip())
    google_id = str(userinfo.get("sub", "")).strip()
    if not email or not google_id:
        raise HTTPException(status_code=400, detail="Google did not return a usable account email.")

    existing_user = db.query(User).filter(or_(User.google_id == google_id, User.email == email)).first()
    if existing_user is not None:
        existing_user.google_id = google_id
        if userinfo.get("picture"):
            existing_user.profile_picture = str(userinfo.get("picture")).strip()
        if not existing_user.is_verified:
            existing_user.is_verified = True
        commit_with_retry(db)
        _clear_google_signup(request)
        request.session["role"] = existing_user.role.value if isinstance(existing_user.role, UserRole) else str(existing_user.role)
        return _complete_google_login(request, db, existing_user)

    preferred_role = str(request.session.pop("google_preferred_role", "")).strip().lower()
    _remember_google_signup(request, userinfo, preferred_role=preferred_role)
    return RedirectResponse(url="/auth/google/choose-role", status_code=303)


@router.get("/choose-role")
def choose_google_role(request: Request):
    google_user = request.session.get("google_signup")
    if not isinstance(google_user, dict):
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        "auth/google_choose_role.html",
        _google_role_context(request, google_user),
    )


@router.post("/complete-signup")
def complete_google_signup(
    request: Request,
    role: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    google_user = request.session.get("google_signup")
    if not isinstance(google_user, dict):
        return RedirectResponse(url="/auth/login", status_code=303)

    normalized_role = str(role).strip().lower()
    if normalized_role not in {UserRole.doctor.value, UserRole.patient.value}:
        return templates.TemplateResponse(
            "auth/google_choose_role.html",
            _google_role_context(request, google_user, error="Choose whether you are signing up as a doctor or a patient."),
            status_code=400,
        )

    normalized_phone = normalize_phone(phone)
    if len(normalized_phone) != 10:
        return templates.TemplateResponse(
            "auth/google_choose_role.html",
            _google_role_context(request, google_user, error="Enter a valid 10-digit phone number to finish Google signup."),
            status_code=400,
        )

    existing = db.query(User).filter(
        or_(User.email == normalize_identifier(google_user["email"]), User.phone == normalized_phone, User.google_id == google_user["google_id"])
    ).first()
    if existing is not None:
        if existing.google_id is None:
            existing.google_id = google_user["google_id"]
        if google_user.get("picture"):
            existing.profile_picture = google_user["picture"]
        if not existing.is_verified:
            existing.is_verified = True
        commit_with_retry(db)
        _clear_google_signup(request)
        return _complete_google_login(request, db, existing)

    user = _build_google_user(
        db,
        email=google_user["email"],
        full_name=google_user["full_name"],
        google_id=google_user["google_id"],
        picture=google_user.get("picture", ""),
        role=normalized_role,
        phone=normalized_phone,
    )
    if user.role == UserRole.doctor:
        ensure_legacy_doctor_for_portal_user(db, user)
    _clear_google_signup(request)
    write_audit_event("google_signup_success", request, user_id=user.id, role=user.role.value)
    track_event("google_signup", role=user.role.value, user_id=user.id)
    return _complete_google_login(request, db, user)
