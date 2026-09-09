from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, get_current_doctor
from app.config import settings
from app.database import SessionLocal, commit_with_retry, get_db
from app.models import Doctor
from app.portal_auth import get_portal_user, require_portal_roles, user_public_context
from models.emr import EMRLabOrder
from models.marketplace import LabStore
from models.user import User
from services.marketplace_service import ensure_marketplace_seed_data, lab_owner_dashboard_payload
from shared.template_engine import render_template


router = APIRouter(tags=["lab-owner"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _lab_context(request: Request, user: User, **extra: Any) -> dict[str, Any]:
    context = {
        "request": request,
        "active_page": "profile",
        "csrf_token": ensure_csrf_token(request),
        **user_public_context(user),
    }
    context.update(extra)
    return context


def _doctor_is_admin(doctor: Doctor) -> bool:
    configured = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    allowed_admins = configured or ["admin@ayurveda.com"]
    dev_admin_by_id = not settings.is_production and int(getattr(doctor, "id", 0) or 0) == 1
    return (doctor.username or "").strip().lower() in allowed_admins or dev_admin_by_id


def require_lab_management_access(request: Request, db: Session = Depends(get_db)) -> User | Doctor:
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        current_role = portal_user.role.value if hasattr(portal_user.role, "value") else str(portal_user.role)
        if current_role in {"lab_owner", "admin"}:
            return portal_user

    try:
        doctor = get_current_doctor(request, db)
    except HTTPException as exc:
        if exc.status_code not in {303, 307}:
            raise
    else:
        if _doctor_is_admin(doctor):
            return doctor

    raise HTTPException(status_code=303, headers={"Location": "/auth/login/lab"})


@router.get("/lab")
def lab_dashboard_page(request: Request, user: User = Depends(require_portal_roles("lab_owner", "admin"))):
    ensure_marketplace_seed_data()
    payload = lab_owner_dashboard_payload()
    return render_template(templates, request,
        "portal/lab_dashboard.html",
        _lab_context(request, user, **payload),
    )


@router.post("/api/lab/register")
def register_lab(payload: dict[str, Any] = Body(...), user: User | Doctor = Depends(require_lab_management_access)):
    db = SessionLocal()
    try:
        store = LabStore(
            owner_id=int(getattr(user, "id")),
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
def lab_appointments_today(lab_id: int | None = Query(default=None), user: User = Depends(require_portal_roles("lab_owner", "admin"))):
    _ = user
    ensure_marketplace_seed_data()
    payload = lab_owner_dashboard_payload(lab_id)
    return JSONResponse({"appointments": [
        {"id": item.id, "lab_name": item.lab_name, "status": item.status, "ordered_at": item.ordered_at.isoformat()}
        for item in payload["today_appointments"]
    ]})


@router.post("/api/lab/reports/upload")
def upload_lab_report(payload: dict[str, Any] = Body(...), user: User = Depends(require_portal_roles("lab_owner", "admin"))):
    _ = user
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
def manage_lab_tests(lab_id: int | None = Query(default=None), user: User | Doctor = Depends(require_lab_management_access)):
    _ = user
    payload = lab_owner_dashboard_payload(lab_id)
    tests = []
    for item in payload["today_appointments"]:
        tests.extend(item.tests_json if isinstance(item.tests_json, list) else [])
    return JSONResponse({"tests": tests, "active_tests": payload["active_tests"]})
