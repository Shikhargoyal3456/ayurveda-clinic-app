from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.database import get_db
from app.portal_auth import dashboard_path_for_role, get_portal_user
from core.dashboards import selector_payload
from services.marketplace_ai import MarketplaceAI
from services.marketplace_service import (
    marketplace_nearby_shops,
)
from shared.template_engine import templates


router = APIRouter(tags=["marketplace"])
marketplace_ai = MarketplaceAI()


@router.get("/portal")
def portal_selector(request: Request, db=Depends(get_db)):
    user = get_portal_user(request, db)
    if user is not None:
        return RedirectResponse(url=dashboard_path_for_role(user.role.value), status_code=303)
    if request.session.get("doctor_id"):
        return RedirectResponse(url="/doctor/dashboard", status_code=303)
    context = selector_payload()
    context.update({"request": request})
    return templates.TemplateResponse(request, "auth/smart_entry.html", context)


@router.post("/api/marketplace/route-order")
async def route_order(payload: dict[str, Any] = Body(...)):
    result = await marketplace_ai.route_order_to_best_pharmacy(payload)
    return JSONResponse(result)


@router.get("/api/marketplace/nearby-shops")
def nearby_shops():
    return JSONResponse(marketplace_nearby_shops())


@router.post("/api/marketplace/dynamic-price")
async def dynamic_price(payload: dict[str, Any] = Body(...)):
    product_id = int(payload.get("product_id", 0) or 0)
    user_context = payload.get("user_context", {}) if isinstance(payload.get("user_context"), dict) else {}
    price = await marketplace_ai.dynamic_pricing(product_id, user_context)
    return JSONResponse({"product_id": product_id, "dynamic_price": price})
