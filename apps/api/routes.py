from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_doctor
from app.database import get_db
from app.models import Doctor
from app.portal_auth import require_portal_roles
from models.marketplace import PharmacyStore
from models.user import User
from core.notifications import notification_center
from core.search import global_search
from services.marketplace_service import (
    doctor_portal_payload,
    lab_owner_dashboard_payload,
    patient_portal_payload,
    pharmacy_inventory_snapshot,
    pharmacy_live_orders,
    pharmacy_owner_dashboard_payload,
)
from services.medicine_management import ensure_pharmacy_store_for_user


router = APIRouter(tags=["api-v1"])


def _role_of(user: User) -> str:
    return getattr(user.role, "value", str(user.role))


def _store_id_for_owner(user: User, db: Session, requested: int) -> int:
    """Resolve which pharmacy store the caller is allowed to read.

    A pharmacy owner is always scoped to their own store; any client-supplied
    ``store_id`` is ignored so one owner cannot read another store's orders,
    revenue, or inventory (cross-tenant IDOR). Admins may target a specific
    store or fall back to the first one.
    """
    if _role_of(user) == "admin":
        if requested:
            return int(requested)
        first = db.query(PharmacyStore).order_by(PharmacyStore.id.asc()).first()
        return int(first.id) if first else 0
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    return int(store.id)


@router.get("/api/v1/patient/orders")
def patient_orders(user: User = Depends(require_portal_roles("patient", "admin"))):
    # Scope the dashboard to the authenticated user rather than a guest identity.
    payload = patient_portal_payload(f"user:{user.id}")
    return JSONResponse({"orders": payload.get("active_orders", [])})


@router.get("/api/v1/pharmacy/inventory")
def pharmacy_inventory(
    store_id: int = Query(default=0),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    return JSONResponse({"inventory": pharmacy_inventory_snapshot(_store_id_for_owner(user, db, store_id))})


@router.get("/api/v1/pharmacy/orders")
def pharmacy_orders(
    store_id: int = Query(default=0),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    return JSONResponse({"orders": pharmacy_live_orders(_store_id_for_owner(user, db, store_id))})


@router.get("/api/v1/pharmacy/analytics")
def pharmacy_analytics(
    store_id: int = Query(default=0),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    resolved = _store_id_for_owner(user, db, store_id)
    payload = pharmacy_owner_dashboard_payload(resolved)
    return JSONResponse(
        {
            "store_id": resolved,
            "total_orders": payload.get("today_orders", 0),
            "revenue": payload.get("today_revenue", 0),
            "stock_alerts": payload.get("low_stock_count", 0),
            "rating": payload.get("rating", 0),
        }
    )


@router.get("/api/v1/doctor/consultations")
def doctor_consultations(doctor: Doctor = Depends(get_current_doctor)):
    payload = doctor_portal_payload(doctor.id)
    appointments = []
    for item in payload.get("appointments", []):
        raw_date = item.get("date")
        appointments.append(
            {
                "id": item.get("id"),
                "date": raw_date.isoformat() if hasattr(raw_date, "isoformat") else raw_date,
                "time": item.get("time"),
                "status": item.get("status"),
            }
        )
    return JSONResponse({"appointments": appointments, "today_consults": payload.get("today_consults", 0)})


@router.get("/api/v1/lab/tests")
def lab_tests(user: User = Depends(require_portal_roles("lab_owner", "admin"))):
    payload = lab_owner_dashboard_payload()
    tests = [
        {
            "id": getattr(item, "id", None),
            "status": getattr(item, "status", ""),
            "ordered_at": getattr(item, "ordered_at").isoformat() if getattr(item, "ordered_at", None) else None,
        }
        for item in payload.get("today_appointments", [])
    ]
    return JSONResponse({"tests": tests, "active_tests": payload.get("active_tests", 0)})


@router.get("/api/v1/delivery/assignments")
def delivery_assignments():
    return JSONResponse(
        {
            "assignments": [
                {"order_id": 9991, "status": "assigned", "eta_minutes": 18},
                {"order_id": 9992, "status": "accepted", "eta_minutes": 26},
            ]
        }
    )


@router.get("/api/v1/notifications")
def notifications(role: str = Query("patient")):
    return JSONResponse({"role": role, "notifications": notification_center(role)})


@router.get("/api/v1/search")
def search(role: str = Query("patient"), q: str = Query("")):
    return JSONResponse(global_search(role, q))
