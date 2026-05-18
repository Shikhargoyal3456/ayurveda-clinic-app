from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.portal_auth import require_portal_roles, user_public_context
from shared.template_engine import templates
from services.profile_service import active_profiles_for_user, profile_avatar_for_relationship, resolve_active_profile
from services.superapp_service import get_dashboard_payload


router = APIRouter(tags=["patient-portal"])


def patient_dashboard_context(request: Request, user=None) -> dict[str, object]:
    is_new_user = not bool(request.session.get("patient_home_seen"))
    request.session["patient_home_seen"] = True
    dashboard = get_dashboard_payload(str(getattr(user, "id", "guest")) if user is not None else "guest")
    subscriptions = list(dashboard.get("subscriptions", []))
    recent_orders = list(dashboard.get("recent_orders", []))
    active_medicines = [
        {
            "name": item.get("medicine_name", "Tracked medicine"),
            "refill_text": ("today" if int(item.get("days_left", 0) or 0) <= 0 else f"in {int(item.get('days_left', 0) or 0)} days"),
            "tone": "yellow" if int(item.get("days_left", 0) or 0) <= 3 else "green",
            "badge": "Refill soon" if int(item.get("days_left", 0) or 0) <= 3 else "On track",
        }
        for item in subscriptions[:3]
    ]
    if not active_medicines:
        active_medicines = [
            {
                "name": "No tracked medicines yet",
                "refill_text": "after your first order",
                "tone": "green",
                "badge": "Waiting for activity",
            }
        ]
    quick_actions = []
    if recent_orders:
        latest_order = recent_orders[0]
        quick_actions.append(
            {
                "title": f"Track order #{latest_order.get('id', '')}",
                "body": f"Current status: {str(latest_order.get('status', 'processing')).replace('_', ' ')}.",
                "tone": "green",
                "href": f"/orders/tracking/{latest_order.get('id')}",
                "action_label": "Track order",
            }
        )
    if subscriptions:
        next_item = subscriptions[0]
        quick_actions.append(
            {
                "title": f"{next_item.get('medicine_name', 'Medicine')} refill window",
                "body": (
                    "Eligible for refill today."
                    if int(next_item.get("days_left", 0) or 0) <= 0
                    else f"Next refill expected in {int(next_item.get('days_left', 0) or 0)} days."
                ),
                "tone": "yellow" if int(next_item.get("days_left", 0) or 0) <= 3 else "green",
                "href": "/my-health",
                "action_label": "View refill timing",
            }
        )
    context: dict[str, object] = {
        "request": request,
        "simple_nav": "home",
        "page_hint": "Order medicines, upload prescriptions, and track your care journey",
        "active_page": "profile",
        "health_score": dashboard.get("health_score", 60),
        "health_message": dashboard.get("health_message", "Your dashboard will personalize as you use more care services."),
        "active_medicines": active_medicines,
        "recent_consults": len(recent_orders),
        "quick_actions": quick_actions,
        "is_new_user": is_new_user,
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
