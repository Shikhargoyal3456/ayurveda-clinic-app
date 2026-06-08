from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import (
    ensure_csrf_token,
    auth_backoff_dependency,
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
from app.database import SessionLocal, commit_with_retry, get_db
from app.portal_auth import (
    build_reset_email,
    build_verification_email,
    clear_portal_session,
    create_portal_session,
    create_user,
    dashboard_path_for_role,
    doctor_dashboard_path,
    ensure_legacy_doctor_for_portal_user,
    get_portal_user,
    normalize_doctor_type,
    normalize_identifier,
    normalize_phone,
    parse_float,
    parse_int,
    resolve_role_slug,
    role_to_slug,
    save_upload,
    serializer_dumps,
    serializer_loads,
    set_user_otp,
    slug_to_role,
    user_public_context,
    validate_portal_password,
    verify_user_password,
    otp_is_valid,
    consume_user_otp,
)
from services.profile_service import active_profiles_for_user, ensure_default_profile, set_active_profile_session
from app.security import hash_refresh_token, invalidate_all_sessions_for_doctor, invalidate_current_session, issue_session_tokens, validate_password_complexity
from app.models import Doctor
from models.user import DoctorProfile, User, UserRole
from services.email_service import EmailService
from shared.template_engine import render_template


logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["auth"])
email_service = EmailService()

VERIFICATION_MAX_AGE_SECONDS = 24 * 60 * 60
RESET_MAX_AGE_SECONDS = 30 * 60
OTP_DIGITS = 6
ROLE_LABELS = {
    UserRole.patient.value: "Patient",
    UserRole.doctor.value: "Doctor",
    UserRole.pharmacy_owner.value: "Pharmacy",
    UserRole.lab_owner.value: "Lab",
    UserRole.delivery_partner.value: "Delivery Partner",
    UserRole.admin.value: "Admin",
}

PORTAL_CONFIG = {
    "patient": {
        "role": UserRole.patient.value,
        "name": "Patient",
        "icon": "fa-user-injured",
        "sample_name": "Ananya Sharma",
        "benefits": [
            "Order medicines in under a minute",
            "Consult verified doctors securely",
            "Track reports, deliveries, and follow-ups",
            "Manage family care from one dashboard",
        ],
    },
    "doctor": {
        "role": UserRole.doctor.value,
        "name": "Doctor",
        "icon": "fa-user-doctor",
        "sample_name": "Dr. Rohan Verma",
        "benefits": [
            "Run digital consultations with structured records",
            "Manage schedules, patients, and follow-ups",
            "Use AI tools with clinician-in-control workflows",
            "Operate a premium telemedicine experience",
        ],
    },
    "pharmacy": {
        "role": UserRole.pharmacy_owner.value,
        "name": "Pharmacy",
        "icon": "fa-store",
        "sample_name": "CityCare Pharmacy",
        "benefits": [
            "Accept online orders with live fulfillment status",
            "Manage inventory and delivery expectations",
            "Grow repeat business with digital storefront tools",
            "Access analytics designed for healthcare commerce",
        ],
    },
    "lab": {
        "role": UserRole.lab_owner.value,
        "name": "Lab",
        "icon": "fa-flask-vial",
        "sample_name": "Precision Diagnostics",
        "benefits": [
            "Handle bookings, reports, and home collections",
            "Coordinate operations from one secure console",
            "Improve turnaround time with digital workflows",
            "Expand to nearby neighborhoods efficiently",
        ],
    },
    "partner": {
        "role": UserRole.delivery_partner.value,
        "name": "Delivery Partner",
        "icon": "fa-motorcycle",
        "sample_name": "Rajesh Kumar",
        "benefits": [
            "Accept medicine delivery tasks with live routing",
            "Track earnings and completed drops transparently",
            "Manage availability from your partner dashboard",
            "Operate with healthcare-grade delivery checks",
        ],
    },
    "admin": {
        "role": UserRole.admin.value,
        "name": "Admin",
        "icon": "fa-user-shield",
        "sample_name": "Kash AI Admin",
        "benefits": [
            "Review platform-wide operations in one place",
            "Monitor users, orders, and service quality",
            "Access admin-only workflows securely",
            "Keep operational controls separate from doctor dashboards",
        ],
    },
}


def _signup_allowed(db: Session) -> bool:
    if settings.allow_public_signup:
        return True
    doctor_exists = db.query(Doctor.id).first() is not None
    return not doctor_exists


def _portal_context(role_slug: str, request: Request, **extra):
    canonical_slug = resolve_role_slug(role_slug)
    config = PORTAL_CONFIG[canonical_slug]
    context = {
        "request": request,
        "role": config["role"],
        "role_slug": canonical_slug,
        "portal_name": config["name"],
        "portal_icon": config["icon"],
        "portal_benefits": config["benefits"],
        "sample_name": config["sample_name"],
        "flash": pop_flash(request),
        "csrf_token": ensure_csrf_token(request),
        "hide_footer": True,
        "nav_profile_href": "/portal",
        "user_name": f"{config['name']} access",
        "user_role": "Secure portal",
        "avatar_label": config["name"][:2].upper(),
    }
    context.update(extra)
    return context


def _portal_slug_or_404(role_slug: str) -> dict[str, str]:
    config = PORTAL_CONFIG.get(resolve_role_slug(role_slug))
    if not config:
        raise HTTPException(status_code=404, detail="Portal not found")
    return config


def _render_smart_login_page(csrf_token: str, preferred_role: str = "", flash: dict[str, str] | None = None) -> HTMLResponse:
    safe_role = escape(preferred_role or "")
    role_title = escape((preferred_role or "").replace("_", " ").title())
    flash_message = escape((flash or {}).get("message", ""))
    flash_category = escape((flash or {}).get("category", "info"))
    role_chip_style = "" if preferred_role else "display:none"
    flash_style = "" if flash_message else "display:none"
    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login | Kash AI</title>
    <meta name="description" content="Login to Kash AI and access your patient or business account.">
    <link rel="icon" type="image/png" href="/static/images/kash-ai-logo.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preconnect" href="https://cdnjs.cloudflare.com">
    <link rel="dns-prefetch" href="https://cdnjs.cloudflare.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css" crossorigin="anonymous" referrerpolicy="no-referrer">
    <style>
    body{{margin:0;font-family:'Inter',sans-serif;background:linear-gradient(180deg,#fffdf7,#eef6ff);color:#0f172a}}
    .smart-login-shell{{min-height:100vh;display:grid;place-items:center;padding:28px 16px}}
    .smart-login-card{{width:min(100%,560px);background:#fff;border:1px solid rgba(15,23,42,.08);border-radius:32px;padding:34px;box-shadow:0 24px 80px rgba(15,23,42,.14)}}
    .login-header{{display:grid;justify-items:center;text-align:center;gap:8px}}
    .login-header h1{{margin:0;color:#0f172a}}
    .login-header .lead-copy{{max-width:44ch;margin:0;color:#475569}}
    .login-brand{{display:inline-flex;align-items:center;justify-content:center;gap:12px;margin-bottom:4px;font-weight:800;color:#0f172a}}
    .login-brand-logo{{width:54px;height:54px;border-radius:16px;object-fit:contain;background:#fff;border:1px solid #dbe3ef;box-shadow:0 12px 24px rgba(15,23,42,.08);padding:6px}}
    .eyebrow{{margin:0;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#0f766e}}
    .hint-chip{{display:inline-flex;margin-top:2px;padding:8px 12px;border-radius:999px;background:#eaf3ff;color:#1d6fd8;font-weight:700}}
    .alert{{margin-top:18px;padding:14px 16px;border-radius:16px;font-weight:600}}
    .alert-info{{background:#eff6ff;color:#1d4ed8}}
    .alert-danger{{background:#fef2f2;color:#b91c1c}}
    .alert-success{{background:#ecfdf5;color:#047857}}
    .alert-warning{{background:#fff7ed;color:#c2410c}}
    .smart-login-form{{display:grid;gap:18px;margin-top:22px}}
    .input-group span{{display:block;margin-bottom:8px;font-weight:600;color:#0f172a}}
    .input-group input{{width:100%;padding:14px 16px;border-radius:16px;border:1px solid #cbd5e1;background:#f8fafc;box-sizing:border-box}}
    .password-wrapper{{position:relative}}
    .toggle-password{{position:absolute;right:14px;top:50%;transform:translateY(-50%);border:none;background:transparent;color:#475569;cursor:pointer}}
    .form-options{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}
    .checkbox-label,.forgot-link,.lookup-result{{font-size:.92rem;color:#475569}}
    .login-btn,.otp-btn,.guest-btn,.lookup-link,.workspace-link{{width:100%;padding:14px 18px;border-radius:16px;font-weight:700;border:none;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;box-sizing:border-box}}
    .login-btn{{background:linear-gradient(135deg,#0f766e,#2563eb);color:#fff}}
    .otp-btn,.guest-btn{{background:#e2e8f0;color:#0f172a}}
    .lookup-link{{background:#eaf3ff;color:#1d4ed8}}
    .workspace-card{{background:linear-gradient(135deg,#f7fbff,#eef8f2)}}
    .workspace-link{{margin-top:14px;background:#0f172a;color:#fff}}
    .divider{{position:relative;text-align:center;color:#64748b}}
    .divider::before{{content:\"\";position:absolute;left:0;right:0;top:50%;height:1px;background:#e2e8f0}}
    .divider span{{position:relative;background:#fff;padding:0 12px}}
    .quick-portal-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:20px}}
    .quick-portal-grid a{{padding:12px 14px;border-radius:16px;background:#f8fbff;border:1px solid #dbe3ef;text-align:center;font-weight:700;color:#0f766e;text-decoration:none}}
    .lookup-card{{margin-top:22px;padding:18px;border-radius:22px;background:#f8fbff;border:1px solid #dbe3ef}}
    .lookup-card p{{margin:8px 0 0}}
    .lookup-row{{display:grid;grid-template-columns:1fr auto;gap:10px;margin-top:12px}}
    .lookup-row input{{padding:14px 16px;border-radius:16px;border:1px solid #cbd5e1}}
    .lookup-actions{{display:grid;gap:10px;margin-top:12px}}
    .register-grid{{display:grid;gap:10px;margin-top:22px}}
    .register-grid a{{font-weight:700;color:#0f766e;text-decoration:none}}
    @media (max-width:560px){{.smart-login-card{{padding:28px 22px}}.lookup-row,.quick-portal-grid{{grid-template-columns:1fr}}}}
    </style>
</head>
<body class="portal-auth-body">
<div class="smart-login-shell">
    <section class="smart-login-card">
        <div class="login-header">
            <div class="login-brand">
                <img src="/static/images/kash-ai-logo.png" alt="Kash AI logo" class="login-brand-logo" loading="lazy">
                <span>Kash AI</span>
            </div>
            <p class="eyebrow">One login for every account</p>
            <h1>Login</h1>
            <p class="lead-copy">Enter your email or phone once. Kash AI will route you to the correct patient or business account without making you guess where to go.</p>
            <div class="hint-chip" style="{role_chip_style}">Preferred account: {role_title}</div>
        </div>
        <div class="alert alert-{flash_category}" style="{flash_style}">{flash_message}</div>
        <form class="smart-login-form" method="post" action="/auth/login">
            <input type="hidden" name="csrf_token" value="{escape(csrf_token)}">
            <input type="hidden" name="role" value="{safe_role}">
            <label class="input-group">
                <span>Email or Phone</span>
                <input type="text" name="identifier" placeholder="Enter your email or phone" required autocomplete="username">
            </label>
            <label class="input-group">
                <span>Password</span>
                <div class="password-wrapper">
                    <input type="password" name="password" id="password" placeholder="Enter your password" required autocomplete="current-password">
                    <button type="button" onclick="togglePassword()" class="toggle-password" aria-label="Toggle password">
                        <i class="fa-solid fa-eye"></i>
                    </button>
                </div>
            </label>
            <div class="form-options">
                <label class="checkbox-label"><input type="checkbox" name="remember_me"> Remember me</label>
                <a href="/auth/forgot-password" class="forgot-link">Forgot Password?</a>
            </div>
            <button type="submit" class="login-btn">Login</button>
            <div class="divider"><span>or</span></div>
            <a class="guest-btn" href="/">Continue as Guest</a>
        </form>
        <div class="quick-portal-grid">
            <a href="/auth/login/patient">Patient login</a>
            <a href="/auth/login/doctor">Doctor login</a>
            <a href="/auth/login/pharmacy">Pharmacy login</a>
            <a href="/auth/login/lab">Lab login</a>
            <a href="/auth/login/partner">Delivery partner login</a>
            <a href="/portal">Business hub</a>
        </div>
        <div class="lookup-card workspace-card">
            <strong>Doctor clinic or admin workspace?</strong>
            <p>If you use the legacy clinic dashboard or your saved admin ID only works there, continue with the secure workspace login.</p>
            <a class="workspace-link" href="/login">Open Doctor / Admin Workspace</a>
        </div>
        <div class="lookup-card">
            <strong>Forgot account type?</strong>
            <p>Enter your email or phone and Kash AI will show the exact portal linked to your account.</p>
            <div class="lookup-row">
                <input type="text" id="accountTypeIdentifier" placeholder="Email or phone">
                <button type="button" class="otp-btn" onclick="lookupAccountType()">Check</button>
            </div>
            <p id="accountTypeResult" class="lookup-result"></p>
            <div id="accountTypeActions" class="lookup-actions"></div>
        </div>
        <div class="register-grid">
            <a href="/auth/register/patient">New patient account</a>
            <a href="/auth/register/doctor">New doctor account</a>
            <a href="/auth/register/pharmacy">New pharmacy account</a>
            <a href="/auth/register/lab">New lab account</a>
            <a href="/auth/register/partner">New delivery partner account</a>
        </div>
    </section>
</div>
<script>
async function lookupAccountType() {{
    const identifier = document.getElementById("accountTypeIdentifier").value.trim();
    const host = document.getElementById("accountTypeResult");
    const actionHost = document.getElementById("accountTypeActions");
    if (!identifier) {{
        host.textContent = "Please enter your email or phone.";
        actionHost.innerHTML = "";
        return;
    }}
    host.textContent = "Checking your account...";
    actionHost.innerHTML = "";
    const response = await fetch("/api/auth/account-type", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{identifier}})
    }});
    const payload = await response.json();
    if (!response.ok || !payload.success) {{
        host.textContent = payload.message || "We could not find your account.";
        actionHost.innerHTML = "";
        return;
    }}
    host.textContent = payload.roles && payload.roles.length
        ? `You are registered as: ${{payload.roles.join(", ")}}`
        : (payload.message || "Continue to secure login.");
    actionHost.innerHTML = (payload.role_cards || []).map((card) => `
        <a class="lookup-link" href="${{card.login_url}}">
            Continue to ${{card.label}} login
        </a>
    `).join("");
}}
function togglePassword() {{
    const password = document.getElementById("password");
    const icon = document.querySelector(".toggle-password i");
    if (password.type === "password") {{
        password.type = "text";
        icon.classList.replace("fa-eye", "fa-eye-slash");
    }} else {{
        password.type = "password";
        icon.classList.replace("fa-eye-slash", "fa-eye");
    }}
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=page_html)


def _build_absolute_url(request: Request, path: str) -> str:
    return str(request.base_url).rstrip("/") + path


def _logout_redirect_for_role(role: str | None) -> str:
    role_login_urls = {
        UserRole.doctor.value: "/auth/login/doctor",
        UserRole.patient.value: "/auth/login/patient",
        UserRole.pharmacy_owner.value: "/auth/login/pharmacy",
        UserRole.lab_owner.value: "/auth/login/lab",
        UserRole.delivery_partner.value: "/auth/login/partner",
        UserRole.admin.value: "/auth/login/admin",
    }
    return role_login_urls.get(str(role or "").strip(), "/auth/login/patient")


def _session_logout_redirect(request: Request) -> str:
    _portal_role = request.session.get("portal_user_role")
    if request.session.get("doctor_id"):
        return "/portal"
    return "/portal"


def _preview_payload(extra: dict[str, str]) -> dict[str, str]:
    return extra if settings.is_testing or not settings.is_production else {}


def _portal_redirect_for_user(request: Request, user: User) -> str:
    role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role_value == UserRole.doctor.value:
        doctor_dashboard = str(request.session.get("portal_doctor_dashboard") or "").strip()
        return doctor_dashboard or dashboard_path_for_role(role_value)
    return dashboard_path_for_role(role_value)


def _activate_linked_workspace_session(request: Request, db: Session, user: User) -> None:
    if user.role == UserRole.doctor:
        legacy_doctor = ensure_legacy_doctor_for_portal_user(db, user)
        if legacy_doctor is not None:
            issue_session_tokens(request, legacy_doctor.id, legacy_doctor.session_version)
            legacy_doctor.failed_login_attempts = 0
            legacy_doctor.locked_until = None
            legacy_doctor.last_login_at = datetime.now(timezone.utc)
            legacy_doctor.refresh_token_hash = hash_refresh_token(str(request.session.get("refresh_token", "")))
            commit_with_retry(db)
    elif user.role == UserRole.admin:
        legacy_admin = db.query(Doctor).filter(Doctor.username == normalize_identifier(user.email)).first()
        if legacy_admin is not None:
            issue_session_tokens(request, legacy_admin.id, legacy_admin.session_version)
            legacy_admin.failed_login_attempts = 0
            legacy_admin.locked_until = None
            legacy_admin.last_login_at = datetime.now(timezone.utc)
            legacy_admin.refresh_token_hash = hash_refresh_token(str(request.session.get("refresh_token", "")))
            commit_with_retry(db)


def _find_portal_user(db: Session, identifier: str, role: str) -> User | None:
    normalized = normalize_identifier(identifier)
    phone = normalize_phone(identifier)
    return (
        db.query(User)
        .filter(
            User.role == role,
            or_(User.email == normalized, User.phone == phone),
        )
        .first()
    )


def _find_portal_users(db: Session, identifier: str) -> list[User]:
    normalized = normalize_identifier(identifier)
    phone = normalize_phone(identifier)
    return (
        db.query(User)
        .filter(or_(User.email == normalized, User.phone == phone))
        .order_by(User.created_at.asc(), User.id.asc())
        .all()
    )


def _role_cards(users: list[User]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for user in users:
        role_value = user.role.value if isinstance(user.role, UserRole) else str(user.role)
        role_slug = role_to_slug(role_value)
        role_label = ROLE_LABELS.get(role_value, role_value.replace("_", " ").title())
        cards.append(
            {
                "role": role_value,
                "role_slug": role_slug,
                "label": role_label,
                "dashboard_url": dashboard_path_for_role(role_value),
                "login_url": f"/auth/login/{role_slug}",
                "register_url": "" if role_value == UserRole.admin.value else f"/auth/register/{role_slug}",
                "description": "Order medicines, upload prescriptions, and track care."
                if role_value == UserRole.patient.value
                else f"Open your {role_label.lower()} workspace safely.",
            }
        )
    return cards


def _legacy_dashboard_path(doctor: Doctor) -> str:
    # Legacy Doctor records do not carry an explicit admin role.
    # Keep them on the doctor dashboard and reserve /admin for portal
    # users whose role is actually UserRole.admin.
    return "/dashboard"


def _try_legacy_workspace_login(request: Request, db: Session, identifier: str, password: str) -> RedirectResponse | None:
    normalized = normalized_username(identifier.strip())
    doctor = db.query(Doctor).filter(Doctor.username == normalized).first()
    if doctor is None:
        return None

    if doctor.locked_until and doctor.locked_until > datetime.now(timezone.utc):
        set_flash(request, "Account temporarily locked after repeated failures.", "danger")
        return RedirectResponse(url="/auth/login", status_code=303)

    if not verify_password(password, doctor.password_hash):
        message = register_login_failure(doctor, normalized, request, db)
        write_audit_event("login_failed", request, username=normalized)
        set_flash(request, message, "danger")
        return RedirectResponse(url="/auth/login", status_code=303)

    if needs_password_rehash(doctor.password_hash):
        doctor.password_hash = hash_password(password)
        commit_with_retry(db)

    initialize_login_session(request, doctor, db)
    doctor.last_login_at = datetime.now(timezone.utc)
    commit_with_retry(db)
    write_audit_event("login_success", request, doctor_id=doctor.id, username=doctor.username)
    track_event("doctor_login", doctor_id=doctor.id, username=doctor.username)
    set_flash(request, f"Welcome back, {doctor.full_name or doctor.username}.", "success")
    return RedirectResponse(url=_legacy_dashboard_path(doctor), status_code=303)


def _complete_portal_login(request: Request, db: Session, user: User, remember_me: bool, audit_name: str = "portal_login_success"):
    _clear_failed_login(user, db)
    user.last_login = datetime.now(timezone.utc)
    commit_with_retry(db)
    # Portal accounts and the legacy doctor/admin workspace use different
    # session keys. Clear the legacy session first so users do not inherit
    # a stale /dashboard or /admin redirect from an earlier login.
    invalidate_current_session(request)
    clear_portal_session(request)
    create_portal_session(request, user, remember_me=remember_me)
    _activate_linked_workspace_session(request, db, user)
    write_audit_event(audit_name, request, user_id=user.id, role=user.role.value)
    track_event("portal_login", role=user.role.value, user_id=user.id)
    redirect_url = dashboard_path_for_role(user.role.value)
    if user.role == UserRole.doctor:
        doctor_profile = getattr(user, "doctor_profile", None) or db.get(DoctorProfile, user.id)
        doctor_type = normalize_doctor_type(
            getattr(doctor_profile, "doctor_type", None),
            getattr(doctor_profile, "specialization", None),
        )
        request.session["portal_doctor_type"] = doctor_type
        request.session["portal_doctor_dashboard"] = doctor_dashboard_path(
            getattr(doctor_profile, "doctor_type", None),
            getattr(doctor_profile, "specialization", None),
        )
    if user.role == UserRole.patient:
        ensure_default_profile(db, user)
        profiles = active_profiles_for_user(db, user.id)
        if len(profiles) > 1:
            redirect_url = "/profiles/select"
        elif profiles:
            set_active_profile_session(request, profiles[0])
    logger.info("portal_login_success email=%s role=%s redirect=%s", user.email, user.role.value, redirect_url)
    return RedirectResponse(url=redirect_url, status_code=303)


def _send_email_message(recipient: str, subject: str, html_body: str) -> None:
    result = email_service._send(subject, html_body, recipient)
    if not result.get("success"):
        logger.info("Portal email send skipped/failed for %s: %s", recipient, result)


def _increment_failed_login(user: User | None, db: Session) -> None:
    if user is None:
        return
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= 8:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    commit_with_retry(db)


def _clear_failed_login(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    commit_with_retry(db)


def _role_specific_profile_data(role: str, form_data: dict[str, str]) -> dict[str, object]:
    if role == UserRole.doctor.value:
        return {
            "doctor_type": normalize_doctor_type(
                form_data.get("doctor_type", ""),
                form_data.get("specialization", ""),
            ),
            "registration_number": form_data.get("registration_number", "").strip() or None,
            "specialization": form_data.get("specialization", "").strip() or None,
            "qualification": form_data.get("qualification", "").strip() or None,
            "experience_years": parse_int(form_data.get("experience_years")),
            "consultation_fee": parse_float(form_data.get("consultation_fee")),
            "available_days": form_data.get("available_days", "").strip() or None,
            "about": form_data.get("about", "").strip() or None,
        }
    if role == UserRole.pharmacy_owner.value:
        return {
            "pharmacy_name": form_data.get("pharmacy_name", "").strip() or None,
            "gst_number": form_data.get("gst_number", "").strip() or None,
            "license_number": form_data.get("license_number", "").strip() or None,
            "address": form_data.get("address", "").strip() or None,
            "delivery_radius_km": parse_int(form_data.get("delivery_radius_km")),
            "minimum_order_amount": parse_float(form_data.get("minimum_order_amount")),
            "latitude": parse_float(form_data.get("latitude")),
            "longitude": parse_float(form_data.get("longitude")),
        }
    if role == UserRole.lab_owner.value:
        return {
            "lab_name": form_data.get("lab_name", "").strip() or None,
            "accreditation_number": form_data.get("accreditation_number", "").strip() or None,
            "address": form_data.get("address", "").strip() or None,
            "latitude": parse_float(form_data.get("latitude")),
            "longitude": parse_float(form_data.get("longitude")),
            "is_home_collection_available": form_data.get("is_home_collection_available") in {"on", "true", "1"},
        }
    if role == UserRole.delivery_partner.value:
        return {
            "vehicle_type": form_data.get("vehicle_type", "bike").strip() or "bike",
            "vehicle_number": form_data.get("vehicle_number", "").strip() or None,
            "dl_number": form_data.get("dl_number", "").strip() or None,
            "current_latitude": parse_float(form_data.get("current_latitude")),
            "current_longitude": parse_float(form_data.get("current_longitude")),
        }
    return {
        "date_of_birth": None,
        "gender": None,
        "blood_group": form_data.get("blood_group", "").strip() or None,
        "emergency_contact_name": form_data.get("emergency_contact_name", "").strip() or None,
        "emergency_contact_phone": normalize_phone(form_data.get("emergency_contact_phone", "")) or None,
        "medical_conditions": form_data.get("medical_conditions", "").strip() or None,
        "allergies": form_data.get("allergies", "").strip() or None,
    }


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        return RedirectResponse(url=_portal_redirect_for_user(request, portal_user), status_code=303)
    if request.session.get("doctor_id"):
        doctor = getattr(request.state, "user", None)
        redirect_url = _legacy_dashboard_path(doctor) if isinstance(doctor, Doctor) else "/dashboard"
        return RedirectResponse(url=redirect_url, status_code=303)
    return render_template(templates, request,
        "login.html",
        {"request": request, "flash": pop_flash(request), "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(..., min_length=3, max_length=120),
    password: str = Form(..., min_length=8, max_length=256),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("login", limit=10, window_seconds=60)),
    ___: None = Depends(auth_backoff_dependency()),
    __: None = Depends(verify_csrf),
):
    portal_users = _find_portal_users(db, username)
    portal_matches = [user for user in portal_users if verify_user_password(user, password)]
    if portal_matches:
        if len(portal_matches) > 1:
            request.session["role_picker_user_ids"] = [user.id for user in portal_matches]
            request.session["role_picker_remember_me"] = False
            logger.info(
                "legacy_login_routed_to_role_picker identifier=%s matched_roles=%s",
                normalize_identifier(username),
                [user.role.value for user in portal_matches],
            )
            return RedirectResponse(url="/auth/choose-role", status_code=303)

        portal_user = portal_matches[0]
        if not portal_user.is_verified:
            set_flash(request, "Your account is under review. We will notify you after verification.", "warning")
            return RedirectResponse(url="/auth/login", status_code=303)
        logger.info(
            "legacy_login_routed_to_portal identifier=%s role=%s",
            normalize_identifier(username),
            portal_user.role.value,
        )
        return _complete_portal_login(request, db, portal_user, remember_me=False, audit_name="legacy_login_portal_handoff")

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
    redirect_url = _legacy_dashboard_path(doctor)
    logger.info("legacy_login_success doctor_id=%s redirect=%s", doctor.id, redirect_url)
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_db)):
    if not _signup_allowed(db):
        set_flash(request, "Public signup is disabled. Contact your administrator.", "warning")
        return RedirectResponse(url="/login", status_code=303)
    return render_template(templates, request,
        "signup.html",
        {
            "request": request,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
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

    valid_specialties = {"ayurveda", "modern_medicine", "homeopathy", "dental", "physiotherapy"}
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
    valid_plans = {"pro", "enterprise"}
    if selected_plan.strip().lower() in valid_plans:
        set_flash(request, f"Account created! Complete your {selected_plan.title()} plan payment to activate.", "success")
        return RedirectResponse(url=f"/pricing?plan={selected_plan.strip().lower()}", status_code=303)

    set_flash(request, "Account created. Please log in.", "success")
    return RedirectResponse(url="/login", status_code=303)


@router.get("/auth/login/{role_slug}")
def portal_login_page(request: Request, role_slug: str, db: Session = Depends(get_db)):
    canonical_slug = resolve_role_slug(role_slug)
    _portal_slug_or_404(canonical_slug)
    if canonical_slug != role_slug:
        return RedirectResponse(url=f"/auth/login/{canonical_slug}", status_code=303)
    user = get_portal_user(request, db)
    if user is not None:
        return RedirectResponse(url=_portal_redirect_for_user(request, user), status_code=303)
    return _render_smart_login_page(
        csrf_token=ensure_csrf_token(request),
        preferred_role=canonical_slug,
        flash=pop_flash(request),
    )


@router.get("/auth/login")
def smart_login_page(request: Request, role: str | None = Query(default=None), db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is not None:
        return RedirectResponse(url=_portal_redirect_for_user(request, user), status_code=303)
    preferred_role = role_to_slug(slug_to_role(role)) if role else ""
    return _render_smart_login_page(
        csrf_token=ensure_csrf_token(request),
        preferred_role=preferred_role,
        flash=pop_flash(request),
    )


@router.post("/auth/login")
@router.post("/auth/login/{role_slug}")
def portal_login(
    request: Request,
    role_slug: str | None = None,
    identifier: str = Form(...),
    password: str = Form(...),
    role: str = Form(""),
    remember_me: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-login", limit=10, window_seconds=60)),
    ___: None = Depends(auth_backoff_dependency()),
    __: None = Depends(verify_csrf),
):
    chosen_role = slug_to_role(role_slug.strip()) if role_slug and role_slug.strip() else (slug_to_role(role.strip()) if role.strip() else "")
    users = [_find_portal_user(db, identifier, chosen_role)] if chosen_role else _find_portal_users(db, identifier)
    users = [user for user in users if user is not None]
    matched_users = [user for user in users if verify_user_password(user, password)]

    if not users or not matched_users:
        if chosen_role in {"", UserRole.doctor.value}:
            legacy_response = _try_legacy_workspace_login(request, db, identifier, password)
            if legacy_response is not None:
                return legacy_response

        target = f"/auth/login/{role_to_slug(chosen_role)}" if chosen_role else "/auth/login"
        for user in users:
            _increment_failed_login(user, db)
        write_audit_event("portal_login_failed", request, identifier=normalize_identifier(identifier), role=chosen_role or "auto")
        set_flash(request, "Invalid login details. Please try again.", "danger")
        return RedirectResponse(url=target, status_code=303)

    if len(matched_users) > 1:
        request.session["role_picker_user_ids"] = [user.id for user in matched_users]
        request.session["role_picker_remember_me"] = remember_me == "on"
        return RedirectResponse(url="/auth/choose-role", status_code=303)

    user = matched_users[0]
    if user is not None and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        target_slug = role_to_slug(chosen_role or user.role.value)
        set_flash(request, "Account temporarily locked after repeated login failures.", "danger")
        return RedirectResponse(url=f"/auth/login/{target_slug}", status_code=303)

    if not user.is_verified:
        set_flash(request, "Your account is under review. We will notify you after verification.", "warning")
        return RedirectResponse(url="/auth/login", status_code=303)

    return _complete_portal_login(request, db, user, remember_me=remember_me == "on")


@router.get("/auth/choose-role")
def choose_role_page(request: Request, db: Session = Depends(get_db)):
    user_ids = request.session.get("role_picker_user_ids", [])
    if not isinstance(user_ids, list) or not user_ids:
        return RedirectResponse(url="/auth/login", status_code=303)
    users = [db.get(User, int(user_id)) for user_id in user_ids]
    users = [user for user in users if user is not None]
    if not users:
        request.session.pop("role_picker_user_ids", None)
        return RedirectResponse(url="/auth/login", status_code=303)
    return render_template(templates, request,
        "auth/role_choice.html",
        {
            "request": request,
            "role_cards": _role_cards(users),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/auth/choose-role")
def choose_role_login(
    request: Request,
    selected_role: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    user_ids = request.session.get("role_picker_user_ids", [])
    allowed_ids = {int(user_id) for user_id in user_ids if str(user_id).isdigit()}
    users = [db.get(User, user_id) for user_id in allowed_ids]
    selected = next(
        (
            user
            for user in users
            if user is not None and (user.role.value if isinstance(user.role, UserRole) else str(user.role)) == selected_role
        ),
        None,
    )
    request.session.pop("role_picker_user_ids", None)
    remember_me = bool(request.session.pop("role_picker_remember_me", False))
    if selected is None:
        set_flash(request, "Please choose your account again.", "warning")
        return RedirectResponse(url="/auth/login", status_code=303)
    return _complete_portal_login(request, db, selected, remember_me=remember_me, audit_name="portal_role_selected")


@router.get("/auth/register")
def portal_register_query_redirect(role: str = Query(...)):
    return RedirectResponse(url=f"/auth/register/{role_to_slug(slug_to_role(role))}", status_code=303)


@router.get("/auth/register/{role_slug}")
def portal_register_page(request: Request, role_slug: str):
    canonical_slug = resolve_role_slug(role_slug)
    _portal_slug_or_404(canonical_slug)
    if canonical_slug != role_slug:
        return RedirectResponse(url=f"/auth/register/{canonical_slug}", status_code=303)
    return render_template(templates, request,
        "auth/portal_register.html",
        {"request": request, **_portal_context(canonical_slug, request)},
    )


@router.post("/auth/register")
@router.post("/api/auth/register")
async def portal_register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    doctor_type: str | None = Form(default=None),
    registration_number: str | None = Form(default=None),
    specialization: str | None = Form(default=None),
    qualification: str | None = Form(default=None),
    experience_years: str | None = Form(default=None),
    consultation_fee: str | None = Form(default=None),
    pharmacy_name: str | None = Form(default=None),
    gst_number: str | None = Form(default=None),
    license_number: str | None = Form(default=None),
    lab_name: str | None = Form(default=None),
    accreditation_number: str | None = Form(default=None),
    vehicle_type: str | None = Form(default=None),
    vehicle_number: str | None = Form(default=None),
    dl_number: str | None = Form(default=None),
    address: str | None = Form(default=None),
    delivery_radius_km: str | None = Form(default=None),
    minimum_order_amount: str | None = Form(default=None),
    latitude: str | None = Form(default=None),
    longitude: str | None = Form(default=None),
    available_days: str | None = Form(default=None),
    about: str | None = Form(default=None),
    emergency_contact_name: str | None = Form(default=None),
    emergency_contact_phone: str | None = Form(default=None),
    medical_conditions: str | None = Form(default=None),
    allergies: str | None = Form(default=None),
    blood_group: str | None = Form(default=None),
    is_home_collection_available: str | None = Form(default=None),
    id_proof: UploadFile | None = File(default=None),
    certificate: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-register", limit=5, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    role = slug_to_role(role)
    allowed_registration_roles = {
        UserRole.patient.value,
        UserRole.doctor.value,
        UserRole.pharmacy_owner.value,
        UserRole.lab_owner.value,
        UserRole.delivery_partner.value,
    }
    if role not in allowed_registration_roles:
        return JSONResponse({"success": False, "error": "Unsupported portal role."}, status_code=400)

    password_errors = validate_portal_password(password)
    if password_errors:
        return JSONResponse({"success": False, "error": " ".join(password_errors)}, status_code=400)

    normalized_email = normalize_identifier(email)
    normalized_phone = normalize_phone(phone)
    if not settings.is_testing and normalized_email.endswith("@example.com"):
        return JSONResponse(
            {
                "success": False,
                "error": "Please use a real email address. Placeholder domains like @example.com cannot receive verification emails.",
            },
            status_code=400,
        )
    existing = db.query(User.id).filter(or_(User.email == normalized_email, User.phone == normalized_phone)).first()
    if existing:
        return JSONResponse({"success": False, "error": "An account with this email or phone already exists."}, status_code=400)

    verification_document_path = save_upload(id_proof, "id-proofs")
    professional_document_path = save_upload(certificate, "certificates")
    form_data = {
        "doctor_type": doctor_type or "",
        "registration_number": registration_number or "",
        "specialization": specialization or "",
        "qualification": qualification or "",
        "experience_years": experience_years or "",
        "consultation_fee": consultation_fee or "",
        "pharmacy_name": pharmacy_name or "",
        "gst_number": gst_number or "",
        "license_number": license_number or "",
        "lab_name": lab_name or "",
        "accreditation_number": accreditation_number or "",
        "vehicle_type": vehicle_type or "",
        "vehicle_number": vehicle_number or "",
        "dl_number": dl_number or "",
        "address": address or "",
        "delivery_radius_km": delivery_radius_km or "",
        "minimum_order_amount": minimum_order_amount or "",
        "latitude": latitude or "",
        "longitude": longitude or "",
        "available_days": available_days or "",
        "about": about or "",
        "emergency_contact_name": emergency_contact_name or "",
        "emergency_contact_phone": emergency_contact_phone or "",
        "medical_conditions": medical_conditions or "",
        "allergies": allergies or "",
        "blood_group": blood_group or "",
        "is_home_collection_available": is_home_collection_available or "",
    }

    user = create_user(
        db,
        full_name=full_name,
        email=normalized_email,
        phone=normalized_phone,
        password=password,
        role=role,
        documents={
            "verification_document_path": verification_document_path,
            "professional_document_path": professional_document_path,
        },
        profile_data=_role_specific_profile_data(role, form_data),
    )
    write_audit_event("portal_signup_success", request, user_id=user.id, role=role)
    track_event("portal_signup", role=role, user_id=user.id)
    if role == UserRole.patient.value:
        payload = {
            "success": True,
            "message": "Account created successfully. You can login now.",
            "redirect_url": "/auth/login",
            "dashboard_url": dashboard_path_for_role(role),
        }
        payload.update(_preview_payload({"verification_token": serializer_dumps({"purpose": "verify-email", "user_id": user.id})}))
        return JSONResponse(payload)

    verification_token = serializer_dumps({"purpose": "verify-email", "user_id": user.id})
    verify_url = _build_absolute_url(request, f"/auth/verify-email?token={verification_token}")
    subject, html_body = build_verification_email(user, verify_url)
    _send_email_message(user.email, subject, html_body)

    payload = {
        "success": True,
        "message": "Registration received. Please verify your email. Professional accounts are reviewed before access.",
        "redirect_url": "/auth/login",
    }
    payload.update(_preview_payload({"verification_token": verification_token}))
    return JSONResponse(payload)


@router.get("/auth/verify-email")
def portal_verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    try:
        payload = serializer_loads(token, VERIFICATION_MAX_AGE_SECONDS)
    except SignatureExpired:
        set_flash(request, "Verification link has expired. Please request a new one.", "danger")
        return RedirectResponse(url="/portal", status_code=303)
    except Exception:
        set_flash(request, "Verification link is invalid.", "danger")
        return RedirectResponse(url="/portal", status_code=303)

    if payload.get("purpose") != "verify-email":
        set_flash(request, "Verification link is invalid.", "danger")
        return RedirectResponse(url="/portal", status_code=303)

    user = db.get(User, int(payload["user_id"]))
    if user is None:
        set_flash(request, "Account no longer exists.", "danger")
        return RedirectResponse(url="/portal", status_code=303)

    user.is_verified = True
    commit_with_retry(db)
    set_flash(request, "Email verified successfully. You can log in now.", "success")
    return RedirectResponse(url="/auth/login", status_code=303)


@router.post("/api/auth/send-otp")
def send_otp(
    request: Request,
    payload: dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-otp", limit=5, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    identifier = str(payload.get("identifier", "")).strip()
    role = slug_to_role(str(payload.get("role", "")).strip())
    user = _find_portal_user(db, identifier, role)
    generic_message = "If the account is eligible, an OTP has been sent."
    if user is None or not user.is_active or not user.is_verified:
        return JSONResponse({"success": True, "message": generic_message})

    otp = "".join(secrets.choice("0123456789") for _ in range(OTP_DIGITS))
    set_user_otp(db, user, otp, purpose="login")
    message = f"Your Kash AI OTP is {otp}. It expires in {10} minutes."
    if "@" in identifier:
        _send_email_message(user.email, "Your Kash AI login OTP", f"<p>{message}</p>")
    else:
        logger.info("OTP generated for phone login user_id=%s", user.id)

    response = {"success": True, "message": generic_message}
    response.update(_preview_payload({"otp_preview": otp}))
    return JSONResponse(response)


@router.post("/api/auth/account-type")
def account_type_lookup(
    payload: dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("account-type-lookup", limit=5, window_seconds=300)),
):
    identifier = str(payload.get("identifier", "")).strip()
    if not identifier:
        return JSONResponse({"success": False, "message": "Please enter your email or phone number."}, status_code=400)
    if settings.is_testing:
        users = _find_portal_users(db, identifier)
        return JSONResponse(
            {
                "success": True,
                "roles": [ROLE_LABELS.get(user.role.value, user.role.value) for user in users],
                "role_cards": _role_cards(users) if users else [{"label": "Continue to secure login", "login_url": "/auth/login"}],
                "message": "We found your account." if users else "If an account exists, continue to secure login to access it.",
            }
        )
    return JSONResponse(
        {
            "success": True,
            "roles": [],
            "role_cards": [{"label": "Continue to secure login", "login_url": "/auth/login"}],
            "message": "If an account exists, continue to secure login to access it.",
        }
    )


@router.post("/api/auth/verify-otp")
def verify_otp_login(
    request: Request,
    payload: dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-otp-verify", limit=8, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    identifier = str(payload.get("identifier", "")).strip()
    otp = str(payload.get("otp", "")).strip()
    role = slug_to_role(str(payload.get("role", "")).strip())
    user = _find_portal_user(db, identifier, role)
    if user is None or not otp_is_valid(user, otp, purpose="login"):
        return JSONResponse({"success": False, "message": "Invalid or expired OTP."}, status_code=400)

    consume_user_otp(db, user)
    user.last_login = datetime.now(timezone.utc)
    commit_with_retry(db)
    invalidate_current_session(request)
    clear_portal_session(request)
    create_portal_session(request, user, remember_me=False)
    _activate_linked_workspace_session(request, db, user)
    write_audit_event("portal_otp_login_success", request, user_id=user.id, role=role)
    redirect_url = dashboard_path_for_role(role)
    logger.info("portal_otp_login_success user_id=%s role=%s redirect=%s", user.id, role, redirect_url)
    return JSONResponse({"success": True, "redirect_url": redirect_url})


@router.get("/auth/forgot-password")
def forgot_password_page(request: Request, role: str | None = Query(default=None)):
    role_slug = role_to_slug(slug_to_role(role)) if role else "patient"
    _portal_slug_or_404(role_slug)
    return render_template(templates, request,
        "auth/forgot_password.html",
        {"request": request, **_portal_context(role_slug, request)},
    )


@router.post("/api/auth/forgot-password")
def forgot_password(
    request: Request,
    identifier: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-forgot-password", limit=5, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    role = slug_to_role(role)
    user = _find_portal_user(db, identifier, role)
    reset_token = ""
    if user is not None and user.is_active:
        reset_token = serializer_dumps({"purpose": "password-reset", "user_id": user.id})
        reset_url = _build_absolute_url(request, f"/auth/reset-password?token={reset_token}")
        subject, html_body = build_reset_email(user, reset_url)
        _send_email_message(user.email, subject, html_body)

    payload = {"success": True, "message": "If an account exists, a reset link has been sent."}
    if reset_token:
        payload.update(_preview_payload({"reset_token": reset_token}))
    return JSONResponse(payload)


@router.get("/auth/reset-password")
def reset_password_page(request: Request, token: str):
    try:
        payload = serializer_loads(token, RESET_MAX_AGE_SECONDS)
    except Exception:
        set_flash(request, "Password reset link is invalid or expired.", "danger")
        return RedirectResponse(url="/portal", status_code=303)

    user_id = int(payload.get("user_id", 0) or 0)
    role_slug = "patient"
    if user_id:
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if user is not None:
                role_slug = role_to_slug(user.role.value)
        finally:
            db.close()
    context = _portal_context(role_slug, request, reset_token=token)
    return render_template(templates, request, "auth/reset_password.html", {"request": request, **context})


@router.post("/api/auth/reset-password")
def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_dependency("portal-reset-password", limit=5, window_seconds=300)),
    __: None = Depends(verify_csrf),
):
    try:
        payload = serializer_loads(token, RESET_MAX_AGE_SECONDS)
    except Exception:
        return JSONResponse({"success": False, "error": "Reset link is invalid or expired."}, status_code=400)

    if payload.get("purpose") != "password-reset":
        return JSONResponse({"success": False, "error": "Reset link is invalid."}, status_code=400)

    errors = validate_portal_password(password)
    if errors:
        return JSONResponse({"success": False, "error": " ".join(errors)}, status_code=400)

    user = db.get(User, int(payload["user_id"]))
    if user is None:
        return JSONResponse({"success": False, "error": "Account not found."}, status_code=404)

    user.password_hash = hash_password(password)
    user.session_version = int(user.session_version or 1) + 1
    user.failed_login_attempts = 0
    user.locked_until = None
    commit_with_retry(db)
    write_audit_event("portal_password_reset", request, user_id=user.id, role=user.role.value)
    return JSONResponse({"success": True, "redirect_url": "/auth/login"})


@router.get("/privacy")
def privacy_page(request: Request):
    return render_template(templates, request, "privacy.html", {"request": request})


@router.post("/logout")
def logout(request: Request, _: None = Depends(verify_csrf)):
    redirect_url = _session_logout_redirect(request)
    write_audit_event("logout", request)
    clear_portal_session(request)
    invalidate_current_session(request)
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/logout")
def logout_get(request: Request):
    redirect_url = _session_logout_redirect(request)
    write_audit_event("logout_get", request)
    clear_portal_session(request)
    invalidate_current_session(request)
    return RedirectResponse(url=redirect_url, status_code=303)


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
    clear_portal_session(request)
    write_audit_event("logout_all_devices", request, doctor_id=doctor.id)
    return RedirectResponse(url="/auth/login/doctor", status_code=303)


@router.post("/auth/logout")
def portal_logout(request: Request, _: None = Depends(verify_csrf)):
    redirect_url = _session_logout_redirect(request)
    clear_portal_session(request)
    invalidate_current_session(request)
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/auth/logout")
def portal_logout_get(request: Request):
    redirect_url = _session_logout_redirect(request)
    clear_portal_session(request)
    invalidate_current_session(request)
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/api/auth/session")
def portal_session_status(request: Request, db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is None:
        return JSONResponse({"authenticated": False})
    payload = {"authenticated": True, "dashboard_url": dashboard_path_for_role(user.role.value)}
    payload.update(user_public_context(user))
    return JSONResponse(payload)
