from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import (
    ensure_csrf_token,
    get_current_doctor,
    hash_password,
    initialize_login_session,
    needs_password_rehash,
    normalized_username,
    pop_flash,
    rate_limit_dependency,
    register_login_failure,
    set_flash,
    verify_csrf,
    verify_password,
)
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Doctor
from app.security import invalidate_all_sessions_for_doctor, invalidate_current_session, validate_password_complexity


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["auth"])


def _signup_allowed(db: Session) -> bool:
    if settings.allow_public_signup:
        return True
    doctor_exists = db.query(Doctor.id).first() is not None
    return not doctor_exists


@router.get("/login")
def login_page(request: Request):
    if request.session.get("doctor_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(..., min_length=3, max_length=120),
    password: str = Form(..., min_length=8, max_length=256),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("login", limit=10, window_seconds=60)),
    __: None = Depends(verify_csrf),
):
    normalized = normalized_username(username.strip())
    doctor = db.query(Doctor).filter(Doctor.username == normalized).first()
    if doctor is not None and doctor.locked_until and doctor.locked_until > datetime.now(timezone.utc):
        set_flash(request, "Account temporarily locked after repeated failures.", "danger")
        return RedirectResponse(url="/login", status_code=303)

    if doctor is None or not verify_password(password, doctor.password_hash):
        message = register_login_failure(doctor, normalized, request, db if doctor is not None else None)
        write_audit_event("login_failed", request, username=normalized)
        set_flash(request, message, "danger")
        return RedirectResponse(url="/login", status_code=303)

    if needs_password_rehash(doctor.password_hash):
        doctor.password_hash = hash_password(password)
        commit_with_retry(db)

    initialize_login_session(request, doctor, db)
    doctor.last_login_at = datetime.now(timezone.utc)
    commit_with_retry(db)
    write_audit_event("login_success", request, doctor_id=doctor.id, username=doctor.username)
    track_event("doctor_login", doctor_id=doctor.id, username=doctor.username)
    set_flash(request, f"Welcome back, {doctor.full_name or doctor.username}.", "success")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_db)):
    if not _signup_allowed(db):
        set_flash(request, "Public signup is disabled. Contact your administrator.", "warning")
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "signup.html",
        {"flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/signup")
def signup(
    request: Request,
    username: str = Form(..., min_length=3, max_length=120),
    password: str = Form(..., min_length=10, max_length=256),
    full_name: str = Form("", max_length=160),
    specialty: str = Form("ayurveda"),
    selected_plan: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("signup", limit=5, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    if not _signup_allowed(db):
        write_audit_event("signup_blocked", request, username=username.strip().lower(), reason="public_signup_disabled")
        set_flash(request, "Public signup is disabled.", "danger")
        return RedirectResponse(url="/login", status_code=303)

    complexity_errors = validate_password_complexity(password)
    if complexity_errors:
        set_flash(request, " ".join(complexity_errors), "danger")
        return RedirectResponse(url="/signup", status_code=303)

    normalized = normalized_username(username.strip())
    existing = db.query(Doctor).filter(Doctor.username == normalized).first()
    if existing:
        write_audit_event("signup_failed", request, username=normalized, reason="username_exists")
        set_flash(request, "Username already exists.", "danger")
        return RedirectResponse(url="/signup", status_code=303)

    valid_specialties = {
        "ayurveda", "modern_medicine", "homeopathy",
        "dental", "physiotherapy"
    }
    if specialty not in valid_specialties:
        specialty = "ayurveda"

    doctor = Doctor(
        username=normalized,
        full_name=full_name.strip(),
        specialty=specialty,
        password_hash=hash_password(password),
    )
    db.add(doctor)
    commit_with_retry(db)
    write_audit_event("signup_success", request, username=normalized, doctor_id=doctor.id)
    track_event("doctor_signup", doctor_id=doctor.id, username=doctor.username, specialty=doctor.specialty)
    valid_plans = {"basic", "pro"}
    if selected_plan.strip().lower() in valid_plans:
        set_flash(
            request,
            f"Account created! Complete your "
            f"{selected_plan.title()} plan payment to activate.",
            "success"
        )
        return RedirectResponse(
            url=f"/pricing?plan={selected_plan.strip().lower()}",
            status_code=303
        )

    set_flash(request, "Account created. Please log in.", "success")
    return RedirectResponse(url="/login", status_code=303)


@router.get("/privacy")
def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@router.get("/logout")
def logout(request: Request):
    write_audit_event("logout", request)
    invalidate_current_session(request)
    return RedirectResponse(url="/login", status_code=303)


@router.post("/logout-all-devices")
def logout_all_devices(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    doctor.session_version += 1
    doctor.refresh_token_hash = None
    commit_with_retry(db)
    invalidate_all_sessions_for_doctor(doctor.id)
    invalidate_current_session(request)
    write_audit_event("logout_all_devices", request, doctor_id=doctor.id)
    return RedirectResponse(url="/login", status_code=303)
