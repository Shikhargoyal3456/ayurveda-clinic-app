from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.portal_auth import require_portal_roles
from models.user import User
from services.ai_pharmacy import ai_pharmacy, build_pharmacy_snapshot, get_competitor_prices
from services.medicine_management import ensure_pharmacy_store_for_user


router = APIRouter(prefix="/api/ai-pharmacy", tags=["AI Pharmacy"])


def _resolve_store(
    db: Session,
    user: User,
    pharmacy_id: int,
):
    _profile, store, pharmacy = ensure_pharmacy_store_for_user(db, user)
    if int(store.id) != int(pharmacy_id):
        raise HTTPException(status_code=403, detail="You can only access your own pharmacy AI insights.")
    return store, pharmacy


@router.get("/demand-forecast/{pharmacy_id}")
async def demand_forecast(
    pharmacy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    store, _pharmacy = _resolve_store(db, user, pharmacy_id)
    snapshot = build_pharmacy_snapshot(db, store.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Pharmacy snapshot not found.")

    forecast = await ai_pharmacy.generate_demand_forecast(store.id, snapshot)
    return {
        "success": True,
        "source": "ai",
        "forecast": forecast,
        "disclaimer": "AI-generated demand forecast based on recent sales and inventory patterns. Use business judgment before placing orders.",
    }


@router.post("/optimize-price")
async def optimize_price(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    medicine_name = str(payload.get("medicine_name") or "").strip()
    current_price = float(payload.get("current_price") or 0)
    demand_score = int(payload.get("demand_score") or 50)
    pharmacy_id = int(payload.get("pharmacy_id") or 0)
    if not medicine_name or current_price <= 0 or pharmacy_id <= 0:
        raise HTTPException(status_code=400, detail="pharmacy_id, medicine_name, and current_price are required.")

    store, pharmacy = _resolve_store(db, user, pharmacy_id)
    competitor_prices = get_competitor_prices(db, medicine_name, int(getattr(pharmacy, "id", 0) or 0))
    result = await ai_pharmacy.optimize_pricing(medicine_name, current_price, competitor_prices, demand_score)
    return {
        "success": True,
        "source": "ai",
        "optimization": {
            **result,
            "competitor_prices": competitor_prices,
            "pharmacy_id": store.id,
        },
        "disclaimer": "AI pricing suggestions should be reviewed against margin, regulation, and local competition.",
    }


@router.get("/order-priorities/{pharmacy_id}")
async def order_priorities(
    pharmacy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    store, _pharmacy = _resolve_store(db, user, pharmacy_id)
    snapshot = build_pharmacy_snapshot(db, store.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Pharmacy snapshot not found.")

    priorities = await ai_pharmacy.prioritize_orders(store.id, snapshot.get("orders", []))
    return {
        "success": True,
        "source": "ai",
        "priorities": priorities,
        "disclaimer": "AI triage is operational guidance only. Final dispensing urgency stays with the pharmacist.",
    }


@router.get("/daily-insights/{pharmacy_id}")
async def daily_insights(
    pharmacy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    store, _pharmacy = _resolve_store(db, user, pharmacy_id)
    snapshot = build_pharmacy_snapshot(db, store.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Pharmacy snapshot not found.")

    insights = await ai_pharmacy.generate_daily_insights(store.id, snapshot)
    return {
        "success": True,
        "source": "ai",
        "insights": insights,
        "disclaimer": "AI-generated business insights based on live pharmacy activity and recent order trends.",
    }
