from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.database import SessionLocal
from app.portal_auth import require_portal_roles, user_public_context
from core.dashboards import pharmacy_dashboard_context
from services.medicine_management import ensure_pharmacy_store_for_user
from shared.template_engine import templates
from shared.template_engine import render_template


router = APIRouter(tags=["pharmacy-portal"])


@router.get("/pharmacy")
@router.get("/portal/pharmacy")
def dashboard(
    request: Request,
    store_id: int | None = Query(default=None),
    user=Depends(require_portal_roles("pharmacy_owner")),
):
    if store_id is None:
        db = SessionLocal()
        try:
            _, store, _ = ensure_pharmacy_store_for_user(db, user)
            store_id = store.id
        finally:
            db.close()
    context = pharmacy_dashboard_context(store_id)
    context.update({"request": request, "active_page": "dashboard", **user_public_context(user)})
    return render_template(templates, request, "portals/pharmacy/dashboard.html", context)
