from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.portal_auth import require_portal_roles, user_public_context
from shared.template_engine import templates
from services.profile_service import active_profiles_for_user, profile_avatar_for_relationship, resolve_active_profile


router = APIRouter(tags=["patient-portal"])


def patient_dashboard_context(request: Request, user=None) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "simple_nav": "home",
        "page_hint": "Order medicines, upload prescriptions, and track your care journey",
        "active_page": "profile",
        "health_score": 85,
        "health_message": "Your recent medicines and deliveries are easy to manage here.",
        "active_medicines": [
            {"name": "Paracetamol", "refill_text": "in 5 days", "tone": "green", "badge": "On track"},
            {"name": "Vitamin D3", "refill_text": "today", "tone": "yellow", "badge": "Refill soon"},
            {"name": "Calcium", "refill_text": "in 10 days", "tone": "green", "badge": "On track"},
        ],
        "recent_consults": 2,
        "quick_actions": [
            {
                "title": "Reorder Paracetamol",
                "body": "You ordered it recently. Buy it again quickly.",
                "tone": "green",
                "href": "/order-medicines?q=Paracetamol",
                "action_label": "Reorder now",
            },
            {
                "title": "Vitamin D3 refill due soon",
                "body": "Your next refill is coming up.",
                "tone": "yellow",
                "href": "/my-health",
                "action_label": "See refill reminder",
            },
        ],
    }
    if user is not None:
        context.update(user_public_context(user))
        active_profile = request.session.get("active_profile_name") or "Select Profile"
        context.update(
            {
                "active_profile_name": active_profile,
                "active_profile_avatar": request.session.get("active_profile_avatar", "👤"),
                "active_profile_relationship": request.session.get("active_profile_relationship", "Self"),
            }
        )
    return context


@router.get("/patient")
@router.get("/portal/patient")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_portal_roles("patient"))):
    profiles = active_profiles_for_user(db, user.id)
    if not profiles:
        return RedirectResponse(url="/profiles/add", status_code=303)
    if len(profiles) > 1 and not request.session.get("active_profile_id"):
        return RedirectResponse(url="/profiles/select", status_code=303)
    active_profile = resolve_active_profile(request, db, user)
    if active_profile is not None:
        request.session["active_profile_name"] = active_profile.profile_name
        request.session["active_profile_avatar"] = profile_avatar_for_relationship(active_profile.relationship, active_profile.profile_avatar)
        request.session["active_profile_relationship"] = active_profile.relationship
    context = patient_dashboard_context(request, user)
    return templates.TemplateResponse(request, "patient_home.html", context)
