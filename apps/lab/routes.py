from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.portal_auth import require_portal_roles, user_public_context
from core.dashboards import lab_dashboard_context
from shared.template_engine import templates
from shared.template_engine import render_template


router = APIRouter(tags=["lab-portal"])


@router.get("/lab")
@router.get("/portal/lab")
def dashboard(
    request: Request,
    lab_id: int | None = Query(default=None),
    user=Depends(require_portal_roles("lab_owner")),
):
    context = lab_dashboard_context(lab_id)
    context.update({"request": request, "active_page": "dashboard", **user_public_context(user)})
    return render_template(templates, request, "portals/lab/dashboard.html", context)
