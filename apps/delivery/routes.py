from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.portal_auth import require_portal_roles, user_public_context
from core.dashboards import delivery_dashboard_context
from shared.template_engine import templates


router = APIRouter(tags=["delivery-portal"])


@router.get("/delivery")
@router.get("/portal/partner")
def dashboard(request: Request, user=Depends(require_portal_roles("delivery_partner"))):
    context = delivery_dashboard_context()
    context.update({"request": request, "active_page": "dashboard", **user_public_context(user)})
    return templates.TemplateResponse(request, "portals/delivery/dashboard.html", context)
