from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

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


router = APIRouter(tags=["api-v1"])


@router.get("/api/v1/patient/orders")
def patient_orders():
    payload = patient_portal_payload()
    return JSONResponse({"orders": payload.get("active_orders", [])})


@router.get("/api/v1/pharmacy/inventory")
def pharmacy_inventory(store_id: int = Query(1)):
    return JSONResponse({"inventory": pharmacy_inventory_snapshot(store_id)})


@router.get("/api/v1/pharmacy/orders")
def pharmacy_orders(store_id: int = Query(1)):
    return JSONResponse({"orders": pharmacy_live_orders(store_id)})


@router.get("/api/v1/pharmacy/analytics")
def pharmacy_analytics(store_id: int = Query(1)):
    payload = pharmacy_owner_dashboard_payload(store_id)
    return JSONResponse(
        {
            "store_id": store_id,
            "total_orders": payload.get("today_orders", 0),
            "revenue": payload.get("today_revenue", 0),
            "stock_alerts": payload.get("low_stock_count", 0),
            "rating": payload.get("rating", 0),
        }
    )


@router.get("/api/v1/doctor/consultations")
def doctor_consultations():
    payload = doctor_portal_payload()
    appointments = [
        {"id": item.id, "date": item.date.isoformat(), "time": item.time, "status": item.status}
        for item in payload.get("appointments", [])
    ]
    return JSONResponse({"appointments": appointments, "today_consults": payload.get("today_consults", 0)})


@router.get("/api/v1/lab/tests")
def lab_tests():
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
