from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, verify_csrf
from app.database import commit_with_retry, get_db
from app.portal_auth import require_portal_roles, user_public_context
from models.user import User, UserProfile
from services.profile_service import (
    MAX_USER_PROFILES,
    active_profiles_for_user,
    count_active_profiles,
    parse_gender,
    profile_pin_matches,
    profile_to_payload,
    resolve_active_profile,
    save_profile_pin,
    set_active_profile_session,
    set_primary_profile,
    touch_profile,
)
from services.cache_service import cache_get_json, cache_set_json
from shared.template_engine import templates


router = APIRouter(tags=["profiles"])


def _profile_page_context(request: Request, db: Session, user: User, **extra):
    profiles = active_profiles_for_user(db, user.id)
    active_profile = resolve_active_profile(request, db, user)
    context = {
        "request": request,
        "profiles": [profile_to_payload(profile) for profile in profiles],
        "active_profile": profile_to_payload(active_profile) if active_profile is not None else None,
        "profile_limit": MAX_USER_PROFILES,
        "csrf_token": ensure_csrf_token(request),
        **user_public_context(user),
        **extra,
    }
    return context


@router.api_route("/profiles/select", methods=["GET", "HEAD"])
def profile_selector(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    profiles = active_profiles_for_user(db, user.id)
    if not profiles:
        return RedirectResponse(url="/profiles/add", status_code=303)
    if len(profiles) == 1:
        set_active_profile_session(request, profiles[0])
        touch_profile(db, profiles[0])
        return RedirectResponse(url="/patient", status_code=303)
    return templates.TemplateResponse(request, "profiles/profile_selector.html", _profile_page_context(request, db, user))


@router.api_route("/profiles/add", methods=["GET", "HEAD"])
def add_profile_page(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    if count_active_profiles(db, user.id) >= MAX_USER_PROFILES:
        return RedirectResponse(url="/profiles/manage", status_code=303)
    return templates.TemplateResponse(
        request,
        "profiles/add_profile.html",
        _profile_page_context(request, db, user, page_mode="create"),
    )


@router.api_route("/profiles/manage", methods=["GET", "HEAD"])
def manage_profiles_page(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    return templates.TemplateResponse(request, "profiles/manage_profiles.html", _profile_page_context(request, db, user))


@router.get("/api/profiles/list")
def list_profiles(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    active_profile = resolve_active_profile(request, db, user)
    cache_key = f"profiles-list:{user.id}:{active_profile.id if active_profile is not None else 0}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached
    profiles = active_profiles_for_user(db, user.id)
    payload = {
        "profiles": [profile_to_payload(profile) for profile in profiles],
        "active_profile_id": active_profile.id if active_profile is not None else None,
    }
    cache_set_json(cache_key, payload, 60)
    return payload


@router.post("/api/profiles/add")
def add_profile(
    request: Request,
    profile_name: str = Form(...),
    relationship: str = Form(...),
    avatar: str = Form(""),
    date_of_birth: str = Form(""),
    gender: str = Form(""),
    blood_group: str = Form(""),
    medical_conditions: str = Form(""),
    allergies: str = Form(""),
    pin_code: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_portal_roles("patient")),
    _: None = Depends(verify_csrf),
):
    if count_active_profiles(db, user.id) >= MAX_USER_PROFILES:
        raise HTTPException(status_code=400, detail="You can create up to 6 profiles.")
    normalized_name = profile_name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Profile name is required.")
    parsed_dob = None
    if date_of_birth.strip():
        parsed_dob = date.fromisoformat(date_of_birth.strip())
    profile = UserProfile(
        user_id=user.id,
        profile_name=normalized_name[:100],
        profile_avatar=avatar.strip() or None,
        relationship=relationship.strip() or "Other",
        date_of_birth=parsed_dob,
        gender=parse_gender(gender),
        blood_group=blood_group.strip() or None,
        medical_conditions=medical_conditions.strip() or None,
        allergies=allergies.strip() or None,
        pin_code=save_profile_pin(pin_code),
        is_primary=count_active_profiles(db, user.id) == 0,
        is_active=True,
    )
    db.add(profile)
    commit_with_retry(db)
    db.refresh(profile)
    set_active_profile_session(request, profile)
    touch_profile(db, profile)
    return RedirectResponse(url="/profiles/select", status_code=303)


@router.post("/api/profiles/select")
async def select_profile(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    data = await request.json()
    profile_id = int(data.get("profile_id") or 0)
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id, UserProfile.user_id == user.id, UserProfile.is_active.is_(True))
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.pin_code:
        request.session["pending_profile_id"] = profile.id
        return JSONResponse({"requires_pin": True, "profile_id": profile.id, "profile_name": profile.profile_name})
    set_active_profile_session(request, profile)
    touch_profile(db, profile)
    return JSONResponse({"success": True, "redirect_url": "/patient"})


@router.post("/api/profiles/verify-pin")
async def verify_profile_pin(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    data = await request.json()
    profile_id = int(data.get("profile_id") or request.session.get("pending_profile_id") or 0)
    pin = str(data.get("pin") or "")
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id, UserProfile.user_id == user.id, UserProfile.is_active.is_(True))
        .first()
    )
    if profile is None or not profile_pin_matches(profile, pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    request.session.pop("pending_profile_id", None)
    set_active_profile_session(request, profile)
    touch_profile(db, profile)
    return JSONResponse({"success": True, "redirect_url": "/patient"})


@router.post("/api/profiles/set-primary")
async def set_profile_primary(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    data = await request.json()
    profile_id = int(data.get("profile_id") or 0)
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id, UserProfile.user_id == user.id, UserProfile.is_active.is_(True))
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    set_primary_profile(db, user.id, profile)
    set_active_profile_session(request, profile)
    touch_profile(db, profile)
    return JSONResponse({"success": True})


@router.post("/api/profiles/delete/{profile_id}")
def delete_profile(profile_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id, UserProfile.user_id == user.id, UserProfile.is_active.is_(True))
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.is_primary:
        raise HTTPException(status_code=400, detail="Primary profile cannot be deleted.")
    profile.is_active = False
    commit_with_retry(db)
    if int(request.session.get("active_profile_id") or 0) == profile.id:
        replacement = resolve_active_profile(request, db, user)
        if replacement is not None:
            set_active_profile_session(request, replacement)
    return RedirectResponse(url="/profiles/manage", status_code=303)
