from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from app.database import SessionLocal, commit_with_retry
from models.emr import EMRLabOrder
from models.marketplace import LabStore
from services.marketplace_service import ensure_marketplace_seed_data, lab_owner_dashboard_payload


router = APIRouter(tags=["lab-owner"])


@router.post("/api/lab/register")
def register_lab(payload: dict[str, Any] = Body(...)):
    db = SessionLocal()
    try:
        store = LabStore(
            owner_id=int(payload.get("owner_id", 1) or 1),
            lab_name=str(payload.get("lab_name", "Integrated Lab")).strip() or "Integrated Lab",
            address=str(payload.get("address", "")).strip(),
            latitude=str(payload.get("latitude", "28.4595")),
            longitude=str(payload.get("longitude", "77.0266")),
            phone=str(payload.get("phone", "9999999999")),
            email=str(payload.get("email", "")),
            accreditation=str(payload.get("accreditation", "NABL")),
            is_home_collection_available=bool(payload.get("is_home_collection_available", True)),
            rating=float(payload.get("rating", 4.6) or 4.6),
        )
        db.add(store)
        commit_with_retry(db)
        db.refresh(store)
        return JSONResponse({"success": True, "lab_id": store.id})
    finally:
        db.close()


@router.get("/api/lab/appointments/today")
def lab_appointments_today(lab_id: int | None = Query(default=None)):
    ensure_marketplace_seed_data()
    payload = lab_owner_dashboard_payload(lab_id)
    return JSONResponse({"appointments": [
        {"id": item.id, "lab_name": item.lab_name, "status": item.status, "ordered_at": item.ordered_at.isoformat()}
        for item in payload["today_appointments"]
    ]})


@router.post("/api/lab/reports/upload")
def upload_lab_report(payload: dict[str, Any] = Body(...)):
    db = SessionLocal()
    try:
        order_id = int(payload.get("order_id", 0) or 0)
        order = db.get(EMRLabOrder, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Lab order not found")
        results = order.results_json if isinstance(order.results_json, list) else []
        results.append(
            {
                "uploaded_at": __import__("datetime").datetime.utcnow().isoformat(),
                "report_name": str(payload.get("report_name", "AI processed report")),
                "summary": str(payload.get("summary", "Report uploaded successfully")),
            }
        )
        order.results_json = results
        order.status = "completed"
        commit_with_retry(db)
        return JSONResponse({"success": True, "lab_order_id": order.id, "status": order.status, "results": results})
    finally:
        db.close()


@router.get("/api/lab/tests/manage")
def manage_lab_tests(lab_id: int | None = Query(default=None)):
    payload = lab_owner_dashboard_payload(lab_id)
    tests = []
    for item in payload["today_appointments"]:
        tests.extend(item.tests_json if isinstance(item.tests_json, list) else [])
    return JSONResponse({"tests": tests, "active_tests": payload["active_tests"]})
