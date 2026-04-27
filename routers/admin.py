from __future__ import annotations

import csv
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, Security, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import aggregate_daily_statistics, track_event
from app.auth import ensure_csrf_token, get_current_doctor, verify_csrf
from app.config import settings
try:
    from app.health import build_health_report
except Exception as exc:
    _health_import_error = str(exc)

    def build_health_report() -> dict[str, str]:
        return {"status": "degraded", "error": f"Health report unavailable: {_health_import_error}"}
from app.models import Appointment, CaseSheet, Doctor, Patient
from app.security import active_session_count, active_sessions_snapshot
from app.database import commit_with_retry, get_db
from models.care_plan import PatientCarePlan
from models.medicine import Medicine, MedicineOrder, Pharmacy, StockAdjustment, utc_now
from models.payment import Payment
from models.prescription import Prescription
from models.subscription import ClinicSubscription
from routers.pharmacy import (
    can_transition,
    _followups_sent_for_order,
    _is_repeat_order,
    _load_order_items,
    _order_followup_anchor,
    _order_has_followups,
    _order_source,
    _patient_reordered_after,
)
from services.analytics_service import (
    get_ai_optimization_insights,
    get_ai_performance_metrics,
    get_alerts,
    get_conversion_rates,
    get_error_summary,
    get_funnel_metrics,
    get_revenue_metrics,
)
from services.compliance_service import get_compliance_status
from services.communication import send_patient_message
from services.delivery_service import get_delivery_statuses
from services.email_service import EmailService
from services.fulfillment_service import get_fulfillment_statuses
from services.inventory_service import auto_restock, get_inventory, get_low_stock, get_restock_status
from services.pharmacy_service import get_pharmacies, register_pharmacy
from services.subscription_service import get_all_subscriptions, get_subscription_recommendations
from services.supplier_service import (
    create_supplier,
    delete_supplier,
    get_all_suppliers,
    get_supplier,
    get_supplier_orders,
    get_suppliers,
    place_supplier_order_safe,
    update_supplier,
)
from services.feature_flags import is_delivery_enabled, is_pricing_enabled, is_supplier_enabled
from services.pricing_service import get_pricing_preview
from services.profit_service import get_profit_metrics


router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
logger = logging.getLogger(__name__)
_ADMIN_ACTION_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
UX_FEEDBACK_LOG = "ux_feedback.jsonl"
security = HTTPBearer(auto_error=False)
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "your-secret-token-here").strip()
email_service = EmailService()


class ActivityConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)
        for connection in stale_connections:
            self.disconnect(connection)


activity_manager = ActivityConnectionManager()


class MedicineUpdateRequest(BaseModel):
    name: str | None = None
    generic_name: str | None = None
    category: str | None = None
    brand: str | None = None
    mrp: int | None = Field(default=None, ge=0)
    price: int | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    unit: str | None = None
    prescription_required: bool | None = None
    description: str | None = None
    image_url: str | None = None
    is_available: bool | None = None


class StockAdjustmentRequest(BaseModel):
    new_stock: int = Field(ge=0)
    reason: str = Field(default="Manual adjustment", max_length=255)


async def _supplier_payload(request: Request, body: dict[str, object] | None = None) -> dict[str, object]:
    # SUPPLIER-FULL-1: Support JSON APIs and admin form submissions without adding dependencies.
    if body:
        return dict(body)
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            payload = await request.json()
            return dict(payload) if isinstance(payload, dict) else {}
        except Exception:
            return {}
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload: dict[str, object] = {}
        for key in form.keys():
            values = form.getlist(key)
            payload[key] = values if len(values) > 1 else values[0]
        return payload
    return {}


def _require_admin(doctor: Doctor) -> Doctor:
    allowed_admins = settings.admin_usernames or ["admin@ayurveda.com"]
    dev_admin_by_id = not settings.is_production and int(getattr(doctor, "id", 0) or 0) == 1
    if doctor.username not in allowed_admins and not dev_admin_by_id:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return doctor


async def verify_admin_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    if credentials and credentials.credentials == ADMIN_API_TOKEN and ADMIN_API_TOKEN and ADMIN_API_TOKEN != "your-secret-token-here":
        return "token"
    doctor = getattr(request.state, "user", None)
    if doctor is not None:
        _require_admin(doctor)
        return "session"
    raise HTTPException(status_code=403, detail="Invalid admin token")


def _database_size() -> int:
    if not settings.database_url.startswith("sqlite:///"):
        return 0
    raw_path = settings.database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = settings.base_dir / path
    return path.stat().st_size if path.exists() else 0


def _medicine_order_is_delayed(order: MedicineOrder) -> bool:
    paid_at = order.paid_at
    if paid_at and paid_at.tzinfo is None:
        paid_at = paid_at.replace(tzinfo=timezone.utc)
    return bool(
        order.payment_status == "paid"
        and order.status == "pending"
        and paid_at
        and datetime.now(timezone.utc) - paid_at > timedelta(hours=2)
    )


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    start = _as_aware(start)
    end = _as_aware(end)
    if start is None or end is None:
        return None
    minutes = (end - start).total_seconds() / 60
    return round(minutes, 2) if minutes >= 0 else None


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _trend_label(current: float, previous: float) -> str:
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"


def _admin_rate_limit(request: Request, action: str, limit: int = 3, window_seconds: int = 60) -> None:
    now = time.time()
    key = f"{action}:{request.client.host if request.client else 'unknown'}"
    entries = _ADMIN_ACTION_BUCKETS[key]
    while entries and now - entries[0] > window_seconds:
        entries.popleft()
    if len(entries) >= limit:
        raise HTTPException(status_code=429, detail="Too many admin actions. Please wait and retry.")
    entries.append(now)


def _feedback_log_path() -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.logs_dir / UX_FEEDBACK_LOG


def _admin_template_context(request: Request, active_page: str = "profile") -> dict[str, object]:
    doctor = getattr(request.state, "user", None)
    return {
        "request": request,
        "active_page": active_page,
        "user_name": getattr(doctor, "full_name", None) or getattr(doctor, "username", "Admin"),
        "user_role": "Operations Console",
        "avatar_label": "AD",
        "nav_profile_href": "/admin",
        "csrf_token": ensure_csrf_token(request),
    }


def _ensure_default_pharmacy(db: Session) -> Pharmacy:
    pharmacy = db.query(Pharmacy).filter(Pharmacy.is_active.is_(True)).order_by(Pharmacy.id.asc()).first()
    if pharmacy is not None:
        return pharmacy
    pharmacy = Pharmacy(
        name="Kash AI Central Pharmacy",
        address="Operations Hub",
        city="New Delhi",
        pincode="110001",
        phone="9999999999",
        whatsapp_number="9999999999",
        drug_licence_number="TEMP-LICENSE-001",
        is_active=True,
    )
    db.add(pharmacy)
    commit_with_retry(db)
    db.refresh(pharmacy)
    return pharmacy


def _safe_price(value: object, default: int = 0) -> int:
    try:
        return max(0, int(round(float(value or default))))
    except (TypeError, ValueError):
        return default


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _medicine_payload(medicine: Medicine) -> dict[str, object]:
    return {
        "id": medicine.id,
        "name": medicine.name,
        "generic_name": medicine.generic_name,
        "category": medicine.category,
        "brand": medicine.brand,
        "mrp": int(medicine.mrp or medicine.price or 0),
        "price": int(medicine.price or 0),
        "stock": int(medicine.stock or 0),
        "unit": medicine.unit,
        "prescription_required": bool(medicine.requires_prescription),
        "description": medicine.description or "",
        "image_url": medicine.image_url or "",
        "pharmacy_id": medicine.pharmacy_id,
        "is_available": bool(medicine.is_available),
    }


def _stock_adjustment_payload(adjustment: StockAdjustment) -> dict[str, object]:
    return {
        "id": adjustment.id,
        "medicine_id": adjustment.medicine_id,
        "previous_stock": adjustment.previous_stock,
        "new_stock": adjustment.new_stock,
        "adjusted_by": adjustment.adjusted_by,
        "reason": adjustment.reason or "",
        "created_at": adjustment.created_at.isoformat() if adjustment.created_at else None,
    }


def _recent_order_payload(order: MedicineOrder) -> dict[str, object]:
    items = _load_order_items(order)
    return {
        "id": order.id,
        "customer_name": order.patient_name,
        "items_count": len(items),
        "items": items,
        "total": int(order.total_amount or 0),
        "status": order.status,
        "payment_status": order.payment_status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "tracking_url": f"/orders/tracking/{order.id}",
    }


async def _save_uploaded_medicine_image(image: UploadFile | None) -> str | None:
    if image is None or not getattr(image, "filename", ""):
        return None
    uploads_dir = settings.static_dir / "uploads" / "medicines"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(image.filename).suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    target = uploads_dir / filename
    content = await image.read()
    target.write_bytes(content)
    return f"/static/uploads/medicines/{filename}"


async def _broadcast_admin_activity(activity_type: str, message: str, extra: dict[str, object] | None = None) -> None:
    payload = {
        "type": activity_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    await activity_manager.broadcast(payload)


def _append_ux_feedback(payload: dict[str, object]) -> None:
    try:
        with _feedback_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception as exc:
        logger.exception("UX feedback write failed: %s", exc)


def _read_ux_feedback(limit: int = 500) -> list[dict[str, object]]:
    path = _feedback_log_path()
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            if not raw_line.strip():
                continue
            item = json.loads(raw_line)
            if isinstance(item, dict):
                rows.append(item)
    except Exception as exc:
        logger.exception("UX feedback read failed: %s", exc)
    return rows


def _ux_feedback_summary() -> dict[str, object]:
    rows = _read_ux_feedback()
    ratings = [_safe_int(row.get("rating")) for row in rows if _safe_int(row.get("rating")) > 0]
    page_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for row in rows:
        page = str(row.get("page") or "unknown")
        issue = str(row.get("issue") or "general")
        page_counts[page] = page_counts.get(page, 0) + 1
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
    return {
        "feedback_count": len(rows),
        "average_rating": _average([float(rating) for rating in ratings]),
        "top_friction_pages": sorted(page_counts.items(), key=lambda item: item[1], reverse=True)[:5],
        "top_issues": sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)[:5],
        "recent_feedback": rows[-20:],
    }


def _order_metadata_value(order: MedicineOrder, key: str) -> object | None:
    for item in _load_order_items(order):
        if isinstance(item, dict) and item.get(key) not in (None, ""):
            return item.get(key)
    return None


def _order_prescription_id(order: MedicineOrder) -> int | None:
    raw_value = _order_metadata_value(order, "prescription_id")
    try:
        return int(raw_value) if raw_value is not None else None
    except (TypeError, ValueError):
        return None


def _is_prescription_order(order: MedicineOrder) -> bool:
    return _order_source(order) == "prescription" or _order_prescription_id(order) is not None


def is_followup_conversion(order: MedicineOrder) -> bool:
    return _order_source(order) == "followup" or bool(_order_metadata_value(order, "followup_key"))


def _payment_link_for_order(order: MedicineOrder) -> str:
    return f"/patient/order/{order.id}/status"


def _payment_pending_message(order: MedicineOrder) -> str:
    return f"Complete your payment to confirm your order: {_payment_link_for_order(order)}"


def _patient_email_for_phone(db: Session, phone: str) -> str:
    try:
        patient = (
            db.query(Patient)
            .filter(Patient.phone == phone)
            .order_by(Patient.created_at.desc(), Patient.id.desc())
            .first()
        )
        return patient.email if patient and patient.email else ""
    except Exception as exc:
        logger.exception("Patient email lookup failed for phone=%s: %s", phone, exc)
        return ""


def _growth_insights(metrics: dict[str, object]) -> list[str]:
    insights: list[str] = []
    if float(metrics.get("conversion_rate") or 0) < 20:
        insights.append("Low prescription->order conversion")
    if float(metrics.get("payment_dropoff_rate") or 0) > 30:
        insights.append("High payment drop-off")
    if float(metrics.get("followup_to_order_rate") or 0) < 10:
        insights.append("Follow-ups not converting")
    return insights


def _inactive_patient_rows(db: Session, days: int = 30, limit: int = 100) -> list[dict[str, object]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows: list[dict[str, object]] = []
    patients = db.query(Patient).filter(Patient.phone != "").order_by(Patient.created_at.desc()).limit(1000).all()
    for patient in patients:
        try:
            orders = (
                db.query(MedicineOrder)
                .filter(MedicineOrder.patient_phone == patient.phone)
                .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
                .all()
            )
            if not orders:
                continue
            last_order = orders[0]
            last_order_at = _as_aware(last_order.created_at)
            if last_order_at and last_order_at < cutoff:
                rows.append(
                    {
                        "patient_id": patient.id,
                        "patient_name": patient.name,
                        "phone": patient.phone,
                        "email": patient.email,
                        "last_order_date": last_order.created_at.isoformat() if last_order.created_at else None,
                        "total_orders": len(orders),
                        "send_checkin": True,
                    }
                )
            if len(rows) >= limit:
                break
        except Exception as exc:
            logger.exception("Inactive patient row failed for patient_id=%s: %s", patient.id, exc)
    return rows


def _deployment_readiness(db: Session) -> dict[str, object]:
    checks: dict[str, str] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    try:
        db.query(func.count(Patient.id)).scalar()
        checks["db"] = "ok"
    except Exception as exc:
        logger.exception("Readiness DB check failed: %s", exc)
        checks["db"] = "error"
        blockers.append("Database is not reachable")

    checks["environment"] = settings.environment
    checks["secret_key"] = "ok" if settings.secret_key != "change-this-secret-before-production" else "default"
    checks["razorpay"] = "configured" if settings.razorpay_key_id and settings.razorpay_key_secret else "missing"
    checks["whatsapp"] = (
        "configured"
        if settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        else "wa_link_fallback"
    )
    checks["email"] = "configured" if settings.email_user and settings.email_password else "missing"
    checks["https_sessions"] = "enabled" if settings.session_https_only else "disabled"

    if settings.is_production and checks["secret_key"] != "ok":
        blockers.append("SECRET_KEY must be changed before production")
    if settings.is_production and not settings.session_https_only:
        blockers.append("HTTPS-only sessions must be enabled in production")
    if checks["razorpay"] == "missing":
        warnings.append("Razorpay credentials are missing")
    if checks["email"] == "missing":
        warnings.append("Email credentials are missing")
    if checks["whatsapp"] != "configured":
        warnings.append("WhatsApp Cloud API is not fully configured")

    return {
        "ready": not blockers,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
    }


def _traffic_snapshot(db: Session) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    last_1h = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)
    return {
        "orders_last_1h": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.created_at >= last_1h.replace(tzinfo=None))
        .scalar()
        or 0,
        "orders_last_24h": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.created_at >= last_24h.replace(tzinfo=None))
        .scalar()
        or 0,
        "payments_last_24h": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.payment_status == "paid", MedicineOrder.paid_at >= last_24h.replace(tzinfo=None))
        .scalar()
        or 0,
        "active_sessions": active_session_count(),
        "growth": _growth_metrics(db),
        "system": _system_health_metrics(db),
    }


def _growth_metrics(db: Session) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    today = now.date()
    last_7d = now - timedelta(days=7)
    previous_7d = now - timedelta(days=14)
    orders = db.query(MedicineOrder).all()
    prescriptions = db.query(Prescription).all()
    prescriptions_by_id = {prescription.id: prescription for prescription in prescriptions}
    total_orders = len(orders)
    repeat_orders = [order for order in orders if _is_repeat_order(order)]
    followup_orders = [order for order in orders if _order_has_followups(order)]
    prescription_orders = [order for order in orders if _is_prescription_order(order)]
    orders_created_not_paid = [order for order in orders if order.payment_status != "paid"]
    followups_sent = sum(len(_followups_sent_for_order(order)) for order in orders)
    followup_conversion_order_ids = {order.id for order in orders if is_followup_conversion(order)}
    prescription_to_order_minutes: list[float] = []
    order_to_payment_minutes: list[float] = []

    for order in orders:
        if _order_has_followups(order):
            anchor = _order_followup_anchor(order)
            if anchor and _patient_reordered_after(db, order, anchor):
                followup_conversion_order_ids.add(order.id)

        prescription_id = _order_prescription_id(order)
        prescription = prescriptions_by_id.get(prescription_id) if prescription_id else None
        if prescription is not None:
            minutes = _minutes_between(prescription.created_at, order.created_at)
            if minutes is not None:
                prescription_to_order_minutes.append(minutes)

        if order.payment_status == "paid":
            minutes = _minutes_between(order.created_at, order.paid_at)
            if minutes is not None:
                order_to_payment_minutes.append(minutes)

    recent_orders_count = sum(1 for order in orders if (_as_aware(order.created_at) or now) >= last_7d)
    previous_orders_count = sum(
        1
        for order in orders
        if previous_7d <= (_as_aware(order.created_at) or now) < last_7d
    )
    recent_revenue = sum(
        float(order.total_amount or 0)
        for order in orders
        if order.payment_status == "paid" and (_as_aware(order.created_at) or now) >= last_7d
    )
    previous_revenue = sum(
        float(order.total_amount or 0)
        for order in orders
        if order.payment_status == "paid" and previous_7d <= (_as_aware(order.created_at) or now) < last_7d
    )

    revenue_today = (
        db.query(func.coalesce(func.sum(MedicineOrder.total_amount), 0))
        .filter(MedicineOrder.payment_status == "paid", func.date(MedicineOrder.paid_at) == today.isoformat())
        .scalar()
        or 0
    )
    revenue_total = (
        db.query(func.coalesce(func.sum(MedicineOrder.total_amount), 0))
        .filter(MedicineOrder.payment_status == "paid")
        .scalar()
        or 0
    )
    followup_triggered_count = len(followup_orders)
    followup_response_rate = (
        round((len(repeat_orders) / followup_triggered_count) * 100, 2)
        if followup_triggered_count
        else 0
    )
    followups_leading_to_order = len(followup_conversion_order_ids)
    metrics = {
        "total_orders": total_orders,
        "prescriptions_created": len(prescriptions),
        "orders_from_prescriptions": len(prescription_orders),
        "conversion_rate": (
            round((len(prescription_orders) / len(prescriptions)) * 100, 2)
            if prescriptions
            else 0
        ),
        "prescription_to_order_conversion_rate": (
            round((len(prescription_orders) / len(prescriptions)) * 100, 2)
            if prescriptions
            else 0
        ),
        "orders_today": db.query(func.count(MedicineOrder.id))
        .filter(func.date(MedicineOrder.created_at) == today.isoformat())
        .scalar()
        or 0,
        "repeat_orders_count": len(repeat_orders),
        "new_orders_count": max(total_orders - len(repeat_orders), 0),
        "orders_created_but_not_paid": len(orders_created_not_paid),
        "orders_created_not_paid": len(orders_created_not_paid),
        "payment_dropoff_rate": (
            round((len(orders_created_not_paid) / total_orders) * 100, 2)
            if total_orders
            else 0
        ),
        "pending_payment_count": sum(1 for order in orders if order.payment_status == "pending"),
        "failed_payment_count": sum(1 for order in orders if order.payment_status == "failed"),
        "revenue_today": float(revenue_today or 0),
        "revenue_total": float(revenue_total or 0),
        "followups_sent": followups_sent,
        "followups_leading_to_order": followups_leading_to_order,
        "followup_to_order_rate": (
            round((followups_leading_to_order / followups_sent) * 100, 2)
            if followups_sent
            else 0
        ),
        "followup_conversion_orders_count": followups_leading_to_order,
        "followup_triggered_count": followup_triggered_count,
        "followup_response_rate": followup_response_rate,
        "avg_prescription_to_order_minutes": _average(prescription_to_order_minutes),
        "avg_order_to_payment_minutes": _average(order_to_payment_minutes),
        "orders_trend": _trend_label(recent_orders_count, previous_orders_count),
        "revenue_trend": _trend_label(recent_revenue, previous_revenue),
        "trend_windows": {
            "last_7_days_orders": recent_orders_count,
            "previous_7_days_orders": previous_orders_count,
            "last_7_days_revenue": round(recent_revenue, 2),
            "previous_7_days_revenue": round(previous_revenue, 2),
        },
        "orders_by_source": {
            "prescription": sum(1 for order in orders if _order_source(order) == "prescription"),
            "order_again": len(repeat_orders),
            "followup": sum(1 for order in orders if _order_source(order) == "followup"),
            "manual": sum(1 for order in orders if _order_source(order) == "manual"),
        },
    }
    metrics["insights"] = _growth_insights(metrics)
    return metrics


def _system_health_metrics(db: Session) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    last_1h = now - timedelta(hours=1)
    paid_pending_orders = (
        db.query(MedicineOrder)
        .filter(MedicineOrder.payment_status == "paid", MedicineOrder.status == "pending")
        .limit(500)
        .all()
    )
    failed_notifications = (
        db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.notification_failed.is_(True))
        .scalar()
        or 0
    )
    delayed_orders = sum(1 for order in paid_pending_orders if _medicine_order_is_delayed(order))
    try:
        growth_metrics = _growth_metrics(db)
        payment_dropoff_rate = float(growth_metrics.get("payment_dropoff_rate") or 0)
    except Exception as exc:
        logger.exception("Payment drop-off health metric failed: %s", exc)
        payment_dropoff_rate = 0
    alerts: list[str] = []
    if failed_notifications > 5:
        alerts.append("High failed notifications")
    if delayed_orders > 5:
        alerts.append("Too many delayed orders")
    if payment_dropoff_rate > 40:
        alerts.append("High payment drop-off")
    return {
        "status": "ok",
        "db": "ok",
        "orders_last_1h": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.created_at >= last_1h.replace(tzinfo=None))
        .scalar()
        or 0,
        "failed_notifications": failed_notifications,
        "delayed_orders": delayed_orders,
        "payment_dropoff_rate": payment_dropoff_rate,
        "alerts": alerts,
    }


def _metrics(db: Session) -> dict[str, object]:
    totals = {
        "patients": db.query(func.count(Patient.id)).scalar() or 0,
        "appointments": db.query(func.count(Appointment.id)).scalar() or 0,
        "case_sheets": db.query(func.count(CaseSheet.id)).scalar() or 0,
        "doctors": db.query(func.count(Doctor.id)).scalar() or 0,
    }
    return {
        "totals": totals,
        "database_size_bytes": _database_size(),
        "active_sessions": active_session_count(),
        "active_session_details": active_sessions_snapshot(),
        "analytics": aggregate_daily_statistics(),
        "health": build_health_report(),
    }


@router.get("/admin")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    payload = _metrics(db)
    track_event("admin_dashboard_viewed", doctor_id=doctor.id)
    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {"doctor": doctor, "metrics": payload, "suppliers": get_all_suppliers()},
    )


@router.get("/api/admin/metrics")
def admin_metrics(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    payload = _metrics(db)
    track_event("admin_metrics_requested", doctor_id=doctor.id)
    return JSONResponse(payload)


@router.get("/admin/funnel-metrics")
def admin_funnel_metrics(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_funnel_metrics_viewed", doctor_id=doctor.id)
    return {"counts": get_funnel_metrics(), "conversion_rates": get_conversion_rates()}


@router.get("/admin/error-metrics")
def admin_error_metrics(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_error_metrics_viewed", doctor_id=doctor.id)
    return get_error_summary()


@router.get("/admin/alerts")
def admin_alerts(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_alerts_viewed", doctor_id=doctor.id)
    return {"alerts": get_alerts()}


@router.get("/admin/ai-metrics")
def admin_ai_metrics(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_ai_metrics_viewed", doctor_id=doctor.id)
    return {"ai_metrics": get_ai_performance_metrics()}


@router.get("/admin/ai-insights")
def admin_ai_insights(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_ai_insights_viewed", doctor_id=doctor.id)
    return {"insights": get_ai_optimization_insights()}


@router.get("/admin/compliance")
def admin_compliance(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_compliance_viewed", doctor_id=doctor.id)
    return {"compliance": get_compliance_status()}


@router.get("/admin/revenue-metrics")
def admin_revenue_metrics(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_revenue_metrics_viewed", doctor_id=doctor.id)
    return {"revenue": get_revenue_metrics()}


@router.get("/admin/pharmacies")
def admin_pharmacies(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_pharmacies_viewed", doctor_id=doctor.id)
    return {"pharmacies": get_pharmacies()}


@router.post("/admin/pharmacy/register")
def admin_register_pharmacy(
    payload: dict[str, object] | None = Body(default=None),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    result = register_pharmacy(payload)
    track_event("admin_pharmacy_register_requested", doctor_id=doctor.id, success=bool(result.get("success")))
    return result


@router.get("/admin/inventory")
def admin_inventory(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_inventory_viewed", doctor_id=doctor.id)
    return {"inventory": get_inventory(), "low_stock": get_low_stock()}


@router.get("/admin/fulfillment")
def admin_fulfillment(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_fulfillment_viewed", doctor_id=doctor.id)
    return {"orders": get_fulfillment_statuses()}


@router.get("/admin/medicine-subscriptions")
def admin_medicine_subscriptions(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    subscriptions = get_all_subscriptions()
    track_event("admin_medicine_subscriptions_viewed", doctor_id=doctor.id, count=len(subscriptions))
    return {"subscriptions": subscriptions, "active_count": sum(1 for item in subscriptions if item.get("active"))}


@router.get("/admin/commerce")
def admin_commerce(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    subscriptions = get_all_subscriptions()
    track_event("admin_commerce_viewed", doctor_id=doctor.id)
    return {
        "pharmacies": get_pharmacies(),
        "inventory": get_inventory(),
        "low_stock": get_low_stock(),
        "fulfillment": get_fulfillment_statuses(),
        "delivery": get_delivery_statuses(),
        "suppliers": get_suppliers(),
        "supplier_orders": get_supplier_orders(),
        "restock": get_restock_status(),
        "profit": get_profit_metrics(),
        "pricing_preview": get_pricing_preview(),
        "api_status": {
            "supplier_api": "enabled" if is_supplier_enabled() else "mock",
            "delivery_api": "enabled" if is_delivery_enabled() else "mock",
            "smart_pricing": "enabled" if is_pricing_enabled() else "disabled",
        },
        "subscriptions": subscriptions,
        "active_subscriptions": sum(1 for item in subscriptions if item.get("active")),
        "subscription_recommendations": get_subscription_recommendations(),
    }


@router.get("/admin/suppliers")
def admin_suppliers(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_suppliers_viewed", doctor_id=doctor.id)
    return {"suppliers": get_all_suppliers(), "supplier_orders": get_supplier_orders()}


@router.get("/admin/supplier/{supplier_id}")
def admin_supplier_detail(
    supplier_id: str,
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    supplier = get_supplier(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    track_event("admin_supplier_detail_viewed", doctor_id=doctor.id, supplier_id=supplier_id)
    return {"supplier": supplier}


@router.post("/admin/supplier/register")
async def admin_register_supplier(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    result = create_supplier(await _supplier_payload(request))
    track_event("admin_supplier_register_requested", doctor_id=doctor.id, success=bool(result.get("success")))
    return result


@router.put("/admin/supplier/{supplier_id}")
async def admin_update_supplier(
    supplier_id: str,
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    result = update_supplier(supplier_id, await _supplier_payload(request))
    track_event("admin_supplier_update_requested", doctor_id=doctor.id, supplier_id=supplier_id, success=bool(result.get("success")))
    if not result.get("success") and result.get("error") == "supplier_not_found":
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return result


@router.post("/admin/supplier/{supplier_id}/order")
async def admin_supplier_order(
    supplier_id: str,
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    supplier = get_supplier(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    data = await _supplier_payload(request)
    medicine = str(data.get("medicine") or data.get("medicine_name") or "General stock").strip()
    quantity = int(data.get("quantity") or 50)
    order = place_supplier_order_safe(medicine, quantity, supplier_id=supplier_id, category=str(data.get("category") or "general"))
    track_event("admin_supplier_order_requested", doctor_id=doctor.id, supplier_id=supplier_id, medicine=medicine, quantity=quantity)
    return {"success": order.get("status") != "failed", "order": order}


@router.delete("/admin/supplier/{supplier_id}")
def admin_delete_supplier(
    supplier_id: str,
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    result = delete_supplier(supplier_id)
    track_event("admin_supplier_delete_requested", doctor_id=doctor.id, supplier_id=supplier_id, success=bool(result.get("success")))
    if not result.get("success") and result.get("error") == "supplier_not_found":
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return result


@router.get("/admin/restock-status")
def admin_restock_status(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_restock_status_viewed", doctor_id=doctor.id)
    return {"restock": get_restock_status(), "triggered": auto_restock()}


@router.get("/admin/delivery-status")
def admin_delivery_status(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_delivery_status_viewed", doctor_id=doctor.id)
    return {"delivery": get_delivery_statuses()}


@router.get("/admin/subscription-recommendations")
def admin_subscription_recommendations(
    user_id: str = "",
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    recommendations = get_subscription_recommendations(user_id or None)
    track_event("admin_subscription_recommendations_viewed", doctor_id=doctor.id, count=len(recommendations))
    return {"recommendations": recommendations}


@router.get("/admin/profit-metrics")
def admin_profit_metrics(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_profit_metrics_viewed", doctor_id=doctor.id)
    return {"profit": get_profit_metrics()}


@router.get("/admin/pricing-preview")
def admin_pricing_preview(
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    track_event("admin_pricing_preview_viewed", doctor_id=doctor.id)
    return {"pricing": get_pricing_preview(), "enabled": is_pricing_enabled()}


@router.get("/admin/growth-metrics")
def admin_growth_metrics(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    try:
        payload = _growth_metrics(db)
    except Exception as exc:
        logger.exception("Growth metrics failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Growth metrics could not be loaded.", "data": {}},
        )
    track_event("admin_growth_metrics_viewed", doctor_id=doctor.id)
    return JSONResponse({"success": True, "message": "Growth metrics loaded.", "data": payload})


@router.websocket("/ws/activity")
async def activity_websocket(websocket: WebSocket):
    await activity_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        activity_manager.disconnect(websocket)
    except Exception:
        activity_manager.disconnect(websocket)


@router.get("/admin/add-medicine")
def add_medicine_page(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    return templates.TemplateResponse("admin/add_medicine.html", _admin_template_context(request))


@router.get("/admin/bulk-upload")
def bulk_upload_page(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    return templates.TemplateResponse("admin/bulk_upload.html", _admin_template_context(request))


@router.get("/admin/activity-dashboard")
def activity_dashboard_page(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    return templates.TemplateResponse("admin/activity_dashboard.html", _admin_template_context(request))


@router.get("/admin/complete")
def complete_admin_page(
    request: Request,
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    return templates.TemplateResponse("admin/complete_admin.html", _admin_template_context(request))


@router.get("/api/admin/medicines")
def get_admin_medicines(
    q: str = "",
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    query = db.query(Medicine).order_by(Medicine.name.asc())
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (Medicine.name.ilike(like))
            | (Medicine.brand.ilike(like))
            | (Medicine.category.ilike(like))
        )
    medicines = query.limit(200).all()
    return JSONResponse([_medicine_payload(medicine) for medicine in medicines])


@router.get("/api/admin/medicines/low-stock")
def get_low_stock_medicines(
    threshold: int = 10,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    medicines = (
        db.query(Medicine)
        .filter(Medicine.stock < max(0, threshold), Medicine.is_available.is_(True))
        .order_by(Medicine.stock.asc(), Medicine.name.asc())
        .limit(200)
        .all()
    )
    return JSONResponse({"threshold": threshold, "medicines": [_medicine_payload(medicine) for medicine in medicines]})


@router.post("/api/admin/medicines/add")
async def add_admin_medicine(
    request: Request,
    name: str = Form(""),
    category: str = Form(""),
    brand: str = Form(""),
    mrp: str = Form(""),
    price: str = Form(""),
    stock: str = Form("100"),
    prescription_required: str = Form("false"),
    description: str = Form(""),
    generic_name: str = Form(""),
    unit: str = Form("unit"),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
    __: str = Depends(verify_admin_access),
):
    _require_admin(doctor)
    if "application/json" in request.headers.get("content-type", "").lower():
        payload = await request.json()
        name = str(payload.get("name", "")).strip()
        category = str(payload.get("category", "wellness")).strip().lower()
        brand = str(payload.get("brand", "")).strip()
        mrp = str(payload.get("mrp", payload.get("price", 0)))
        price = str(payload.get("price", 0))
        stock = str(payload.get("stock", 100))
        prescription_required = str(payload.get("prescription_required", False))
        description = str(payload.get("description", "")).strip()
        generic_name = str(payload.get("generic_name", "")).strip()
        unit = str(payload.get("unit", "unit")).strip() or "unit"
        image = None

    name = name.strip()
    if not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "Medicine name is required."})

    normalized_stock = max(0, _safe_price(stock, 100))
    pharmacy = _ensure_default_pharmacy(db)
    image_url = await _save_uploaded_medicine_image(image)
    medicine = Medicine(
        name=name,
        generic_name=generic_name.strip() or None,
        category=(category.strip().lower() or "wellness"),
        brand=brand.strip() or None,
        mrp=_safe_price(mrp, _safe_price(price, 0)),
        price=_safe_price(price, 0),
        stock=normalized_stock,
        unit=unit.strip() or "unit",
        requires_prescription=_normalize_bool(prescription_required),
        is_available=normalized_stock > 0,
        description=description.strip() or None,
        image_url=image_url,
        pharmacy_id=pharmacy.id,
    )
    db.add(medicine)
    commit_with_retry(db)
    db.refresh(medicine)
    await _broadcast_admin_activity(
        "medicine_added",
        f"New medicine added: {medicine.name}",
        {"medicine_id": medicine.id},
    )
    return JSONResponse({"success": True, "medicine_id": medicine.id, "medicine": _medicine_payload(medicine)})


@router.post("/api/admin/medicines/bulk-upload")
async def bulk_upload_medicines(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
    __: str = Depends(verify_admin_access),
):
    _require_admin(doctor)
    if not file.filename.lower().endswith(".csv"):
        return JSONResponse(status_code=400, content={"success": False, "error": "Please upload a CSV file."})

    pharmacy = _ensure_default_pharmacy(db)
    raw_text = (await file.read()).decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(StringIO(raw_text))
    added = 0
    failed = 0
    failures: list[dict[str, object]] = []

    for index, row in enumerate(reader, start=2):
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                raise ValueError("Missing medicine name")
            normalized_stock = max(0, _safe_price(row.get("stock"), 100))
            medicine = Medicine(
                name=name,
                generic_name=str(row.get("generic_name", "")).strip() or None,
                category=str(row.get("category", "wellness")).strip().lower() or "wellness",
                brand=str(row.get("brand", "")).strip() or None,
                mrp=_safe_price(row.get("mrp"), _safe_price(row.get("price"), 0)),
                price=_safe_price(row.get("price"), 0),
                stock=normalized_stock,
                unit=str(row.get("unit", "unit")).strip() or "unit",
                requires_prescription=_normalize_bool(row.get("prescription_required")),
                is_available=normalized_stock > 0,
                description=str(row.get("description", "")).strip() or None,
                image_url=str(row.get("image_url", "")).strip() or None,
                pharmacy_id=pharmacy.id,
            )
            db.add(medicine)
            added += 1
        except Exception as exc:
            failed += 1
            failures.append({"row": index, "error": str(exc)})

    commit_with_retry(db)
    await _broadcast_admin_activity(
        "bulk_upload",
        f"Bulk medicine upload completed: {added} added, {failed} failed",
        {"added": added, "failed": failed},
    )
    return JSONResponse({"success": True, "added": added, "failed": failed, "failures": failures[:20]})


@router.post("/api/admin/medicines/bulk")
async def bulk_add_medicines_json(
    request: Request,
    payload: dict[str, object] = Body(default={}),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    __: str = Depends(verify_admin_access),
):
    _require_admin(doctor)
    medicines = payload.get("medicines", [])
    if not isinstance(medicines, list):
        raise HTTPException(status_code=400, detail="medicines must be a list")

    pharmacy = _ensure_default_pharmacy(db)
    added = 0
    failed = 0
    failures: list[dict[str, object]] = []

    for index, row in enumerate(medicines):
        try:
            if not isinstance(row, dict):
                raise ValueError("Each medicine must be an object")
            name = str(row.get("name", "")).strip()
            if not name:
                raise ValueError("Missing medicine name")
            normalized_stock = max(0, _safe_price(row.get("stock"), 100))
            medicine = Medicine(
                name=name,
                generic_name=str(row.get("generic_name", "")).strip() or None,
                category=str(row.get("category", "wellness")).strip().lower() or "wellness",
                brand=str(row.get("brand", "")).strip() or None,
                mrp=_safe_price(row.get("mrp"), _safe_price(row.get("price"), 0)),
                price=_safe_price(row.get("price"), 0),
                stock=normalized_stock,
                unit=str(row.get("unit", "unit")).strip() or "unit",
                requires_prescription=_normalize_bool(row.get("prescription_required")),
                is_available=normalized_stock > 0,
                description=str(row.get("description", "")).strip() or None,
                image_url=str(row.get("image_url", "")).strip() or None,
                pharmacy_id=pharmacy.id,
            )
            db.add(medicine)
            added += 1
        except Exception as exc:
            failed += 1
            failures.append({"index": index, "error": str(exc)})

    commit_with_retry(db)
    await _broadcast_admin_activity(
        "bulk_upload",
        f"Bulk JSON medicine sync completed: {added} added, {failed} failed",
        {"added": added, "failed": failed},
    )
    write_audit_event("admin_bulk_medicine_import", request, added=added, failed=failed)
    return JSONResponse({"success": True, "added": added, "failed": failed, "failures": failures[:20]})


@router.put("/api/admin/medicines/{medicine_id}")
async def update_medicine(
    medicine_id: int,
    updates: MedicineUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: str = Depends(verify_admin_access),
):
    doctor = _require_admin(doctor)
    medicine = db.get(Medicine, medicine_id)
    if medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")

    data = updates.model_dump(exclude_unset=True)
    previous_stock = int(medicine.stock or 0)
    for field, value in data.items():
        if field == "prescription_required":
            setattr(medicine, "requires_prescription", bool(value))
        else:
            setattr(medicine, field, value)
    if "stock" in data:
        medicine.is_available = int(medicine.stock or 0) > 0
        adjustment = StockAdjustment(
            medicine_id=medicine.id,
            previous_stock=previous_stock,
            new_stock=int(medicine.stock or 0),
            adjusted_by=int(getattr(doctor, "id", 0) or 0),
            reason="Inventory update",
        )
        db.add(adjustment)

    commit_with_retry(db)
    db.refresh(medicine)
    await _broadcast_admin_activity("medicine_updated", f"Medicine updated: {medicine.name}", {"medicine_id": medicine.id})
    write_audit_event("admin_medicine_updated", request, medicine_id=medicine.id)
    logger.info("Medicine %s updated by admin %s", medicine.id, doctor.id)
    return JSONResponse({"success": True, "medicine": _medicine_payload(medicine)})


@router.delete("/api/admin/medicines/{medicine_id}")
async def delete_medicine(
    medicine_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: str = Depends(verify_admin_access),
):
    doctor = _require_admin(doctor)
    medicine = db.get(Medicine, medicine_id)
    if medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    medicine.is_available = False
    commit_with_retry(db)
    db.refresh(medicine)
    await _broadcast_admin_activity("medicine_archived", f"Medicine archived: {medicine.name}", {"medicine_id": medicine.id})
    write_audit_event("admin_medicine_archived", request, medicine_id=medicine.id)
    logger.info("Medicine %s archived by admin %s", medicine.id, doctor.id)
    return JSONResponse({"success": True, "medicine": _medicine_payload(medicine)})


@router.post("/api/admin/medicines/{medicine_id}/adjust-stock")
async def adjust_stock(
    medicine_id: int,
    adjustment: StockAdjustmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: str = Depends(verify_admin_access),
):
    doctor = _require_admin(doctor)
    medicine = db.get(Medicine, medicine_id)
    if medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")

    previous_stock = int(medicine.stock or 0)
    medicine.stock = int(adjustment.new_stock)
    medicine.is_available = medicine.stock > 0
    record = StockAdjustment(
        medicine_id=medicine.id,
        previous_stock=previous_stock,
        new_stock=medicine.stock,
        adjusted_by=int(getattr(doctor, "id", 0) or 0),
        reason=adjustment.reason,
    )
    db.add(record)
    commit_with_retry(db)
    db.refresh(record)
    db.refresh(medicine)
    await _broadcast_admin_activity(
        "stock_adjusted",
        f"Stock updated for {medicine.name}: {previous_stock} -> {medicine.stock}",
        {"medicine_id": medicine.id},
    )
    write_audit_event("admin_stock_adjusted", request, medicine_id=medicine.id, new_stock=medicine.stock)
    logger.info("Stock adjusted for medicine %s by admin %s", medicine.id, doctor.id)
    return JSONResponse({"success": True, "medicine": _medicine_payload(medicine), "adjustment": _stock_adjustment_payload(record)})


@router.get("/api/admin/medicines/{medicine_id}/adjustments")
def stock_adjustment_history(
    medicine_id: int,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    adjustments = (
        db.query(StockAdjustment)
        .filter(StockAdjustment.medicine_id == medicine_id)
        .order_by(StockAdjustment.created_at.desc(), StockAdjustment.id.desc())
        .limit(100)
        .all()
    )
    return JSONResponse({"adjustments": [_stock_adjustment_payload(item) for item in adjustments]})


@router.get("/api/admin/stats")
def admin_activity_stats(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    today = datetime.now(timezone.utc).date()
    orders_today = (
        db.query(func.count(MedicineOrder.id))
        .filter(func.date(MedicineOrder.created_at) == today.isoformat())
        .scalar()
        or 0
    )
    revenue_today = int(
        db.query(func.coalesce(func.sum(MedicineOrder.total_amount), 0))
        .filter(func.date(MedicineOrder.created_at) == today.isoformat())
        .scalar()
        or 0
    )
    medicines_sold = 0
    recent_orders = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).limit(100).all()
    for order in recent_orders:
        medicines_sold += sum(int(item.get("qty", 1) or 1) for item in _load_order_items(order))
    order_counts = {
        status: db.query(func.count(MedicineOrder.id)).filter(MedicineOrder.status == status).scalar() or 0
        for status in ["pending", "confirmed", "packed", "dispatched", "delivered", "cancelled"]
    }
    return JSONResponse(
        {
            "active_users": active_session_count(),
            "orders_today": orders_today,
            "revenue_today": revenue_today,
            "medicines_sold": medicines_sold,
            "orders": order_counts,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/api/admin/orders/recent")
def admin_recent_orders(
    limit: int = 20,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    orders = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return JSONResponse([_recent_order_payload(order) for order in orders])


@router.put("/api/orders/{order_id}/status")
async def admin_update_order_status(
    order_id: int,
    request: Request,
    payload: dict[str, object] = Body(default={}),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    __: str = Depends(verify_admin_access),
):
    _require_admin(doctor)
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    requested_status = str(payload.get("status", "")).strip().lower()
    normalized_status = {"processing": "confirmed", "shipped": "dispatched"}.get(requested_status, requested_status)
    if normalized_status not in {"pending", "confirmed", "dispatched", "delivered", "cancelled"}:
        raise HTTPException(status_code=400, detail="Unsupported order status.")

    if normalized_status in {"confirmed", "dispatched", "delivered"} and not can_transition(order.status, normalized_status):
        raise HTTPException(status_code=400, detail=f"Order cannot move from {order.status} to {normalized_status}.")

    if normalized_status == "confirmed" and order.payment_status != "paid":
        order.payment_status = "paid"
        if order.paid_at is None:
            order.paid_at = utc_now()

    order.status = normalized_status
    if normalized_status == "cancelled":
        order.notification_failed = False

    commit_with_retry(db)
    db.refresh(order)
    await _broadcast_admin_activity(
        "order_status_updated",
        f"Order #{order.id} updated to {order.status}",
        {"order_id": order.id, "status": order.status},
    )
    patient = db.query(Patient).filter(Patient.phone == order.patient_phone).first()
    if patient and patient.email:
        await email_service.send_order_status_update(order.id, order.status, patient.email)
    write_audit_event("admin_order_status_updated", request, order_id=order.id, status=order.status)
    logger.info("Admin %s updated order %s to %s", doctor.id, order.id, order.status)
    return JSONResponse({"success": True, "order": _recent_order_payload(order)})


@router.post("/api/orders/{order_id}/notify")
async def admin_notify_order_customer(
    order_id: int,
    request: Request,
    payload: dict[str, object] = Body(default={}),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    __: str = Depends(verify_admin_access),
):
    _require_admin(doctor)
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    status = str(payload.get("status", order.status)).strip().lower() or order.status
    message = f"Order #{order.id} update: your medicine order is now {status}."
    result = await run_in_threadpool(
        send_patient_message,
        order.patient_phone,
        "",
        message,
        "Kash AI order update",
    )
    await _broadcast_admin_activity(
        "order_notified",
        f"Customer notified for order #{order.id}",
        {"order_id": order.id, "status": status},
    )
    write_audit_event("admin_order_customer_notified", request, order_id=order.id, status=status)
    return JSONResponse({"success": True, "result": result})


@router.get("/api/admin/orders/export")
def export_orders(
    format: str = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    query = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc())
    if start_date:
        query = query.filter(func.date(MedicineOrder.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(MedicineOrder.created_at) <= end_date)
    orders = query.limit(5000).all()

    if format == "excel":
        try:
            from openpyxl import Workbook
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Excel export unavailable: {exc}") from exc
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Orders"
        sheet.append(["Order ID", "Customer", "Phone", "Status", "Payment", "Total", "Created At"])
        for order in orders:
            sheet.append([
                order.id,
                order.patient_name,
                order.patient_phone,
                order.status,
                order.payment_status,
                order.total_amount,
                order.created_at.isoformat() if order.created_at else "",
            ])
        from io import BytesIO
        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=orders_export.xlsx"},
        )

    csv_stream = StringIO()
    writer = csv.writer(csv_stream)
    writer.writerow(["order_id", "customer", "phone", "status", "payment_status", "total_amount", "created_at"])
    for order in orders:
        writer.writerow([
            order.id,
            order.patient_name,
            order.patient_phone,
            order.status,
            order.payment_status,
            order.total_amount,
            order.created_at.isoformat() if order.created_at else "",
        ])
    return StreamingResponse(
        iter([csv_stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_export.csv"},
    )


@router.get("/api/admin/medicines/export")
def export_medicines(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    _require_admin(doctor)
    medicines = db.query(Medicine).order_by(Medicine.name.asc()).limit(5000).all()
    csv_stream = StringIO()
    writer = csv.writer(csv_stream)
    writer.writerow(["id", "name", "category", "brand", "mrp", "price", "stock", "unit", "prescription_required", "is_available"])
    for medicine in medicines:
        writer.writerow([
            medicine.id,
            medicine.name,
            medicine.category,
            medicine.brand or "",
            medicine.mrp or medicine.price or 0,
            medicine.price or 0,
            medicine.stock or 0,
            medicine.unit,
            bool(medicine.requires_prescription),
            bool(medicine.is_available),
        ])
    return StreamingResponse(
        iter([csv_stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=medicines_export.csv"},
    )


@router.get("/health/system")
def system_health(db: Session = Depends(get_db)):
    try:
        payload = _system_health_metrics(db)
        return JSONResponse(payload)
    except Exception as exc:
        logger.exception("System health check failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "status": "degraded",
                "db": "error",
                "orders_last_1h": 0,
                "failed_notifications": 0,
                "delayed_orders": 0,
                "payment_dropoff_rate": 0,
                "alerts": ["System health check failed"],
            },
        )


@router.get("/health/readiness")
def readiness_health(db: Session = Depends(get_db)):
    try:
        payload = _deployment_readiness(db)
        return JSONResponse(
            {
                "success": payload["ready"],
                "message": "Deployment readiness checked.",
                "data": payload,
            }
        )
    except Exception as exc:
        logger.exception("Readiness health check failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Deployment readiness check failed.",
                "data": {"ready": False, "checks": {}, "warnings": [], "blockers": ["Readiness check failed"]},
            },
        )


@router.post("/feedback/ux")
def capture_ux_feedback(
    request: Request,
    page: str = Form("unknown"),
    rating: int = Form(0),
    issue: str = Form("general"),
    message: str = Form(""),
    contact: str = Form(""),
):
    _admin_rate_limit(request, "ux_feedback", limit=10, window_seconds=60)
    rating = max(0, min(int(rating or 0), 5))
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "page": page.strip()[:120] or "unknown",
        "rating": rating,
        "issue": issue.strip()[:80] or "general",
        "message": message.strip()[:1000],
        "contact": contact.strip()[:120],
        "client": request.client.host if request.client else "unknown",
    }
    _append_ux_feedback(payload)
    track_event("ux_feedback_submitted", page=payload["page"], rating=rating, issue=payload["issue"])
    return JSONResponse(
        {
            "success": True,
            "message": "Feedback received.",
            "data": {"received": True},
        }
    )


@router.get("/admin/user-validation-insights")
def user_validation_insights(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    try:
        payload = {
            "ux_feedback": _ux_feedback_summary(),
            "growth": _growth_metrics(db),
            "readiness": _deployment_readiness(db),
        }
    except Exception as exc:
        logger.exception("User validation insights failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "User validation insights could not be loaded.", "data": {}},
        )
    track_event("admin_user_validation_insights_viewed", doctor_id=doctor.id)
    return JSONResponse({"success": True, "message": "User validation insights loaded.", "data": payload})


@router.get("/admin/traffic-snapshot")
def admin_traffic_snapshot(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    try:
        payload = _traffic_snapshot(db)
    except Exception as exc:
        logger.exception("Traffic snapshot failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Traffic snapshot could not be loaded.", "data": {}},
        )
    track_event("admin_traffic_snapshot_viewed", doctor_id=doctor.id)
    return JSONResponse({"success": True, "message": "Traffic snapshot loaded.", "data": payload})


@router.post("/admin/trigger-payment-reminders")
async def trigger_payment_reminders(
    request: Request,
    limit: int = Form(25),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    doctor = _require_admin(doctor)
    _admin_rate_limit(request, "payment_reminders", limit=2, window_seconds=60)
    limit = max(1, min(limit, 50))
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        orders = (
            db.query(MedicineOrder)
            .filter(
                MedicineOrder.payment_status == "pending",
                MedicineOrder.created_at >= recent_cutoff.replace(tzinfo=None),
            )
            .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.exception("Payment reminder order lookup failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Payment reminders could not be loaded.", "data": {}},
        )

    if not orders:
        return JSONResponse({"success": True, "message": "No users to notify", "data": {"sent": [], "skipped": 0}})

    sent: list[dict[str, object]] = []
    skipped = 0
    for order in orders:
        try:
            message = _payment_pending_message(order)
            email = _patient_email_for_phone(db, order.patient_phone)
            result = await run_in_threadpool(
                send_patient_message,
                order.patient_phone,
                email,
                message,
                "Complete your Kash AI payment",
            )
            if not result.get("whatsapp") and not result.get("email"):
                order.notification_failed = True
                skipped += 1
            sent.append({"order_id": order.id, "result": result})
            logger.info("Payment reminder sent for order_id=%s result=%s", order.id, result)
        except Exception as exc:
            logger.exception("Payment reminder failed for order_id=%s: %s", order.id, exc)
            order.notification_failed = True
            skipped += 1

    commit_with_retry(db)
    track_event("admin_payment_reminders_triggered", doctor_id=doctor.id, count=len(sent), skipped=skipped)
    return JSONResponse(
        {
            "success": True,
            "message": "Payment reminder sent" if sent else "No users to notify",
            "data": {"sent": sent, "skipped": skipped},
        }
    )


@router.get("/admin/inactive-patients")
def inactive_patients(
    days: int = 30,
    limit: int = 100,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    try:
        rows = _inactive_patient_rows(db, days=max(1, days), limit=max(1, min(limit, 200)))
    except Exception as exc:
        logger.exception("Inactive patients lookup failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Inactive patients could not be loaded.", "data": {}},
        )
    track_event("admin_inactive_patients_viewed", doctor_id=doctor.id, count=len(rows))
    return JSONResponse(
        {
            "success": True,
            "message": "Inactive patients loaded." if rows else "No users to notify",
            "data": {"patients": rows},
        }
    )


@router.post("/admin/send-checkin/{patient_id}")
async def send_patient_checkin(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    doctor = _require_admin(doctor)
    _admin_rate_limit(request, f"checkin:{patient_id}", limit=3, window_seconds=60)
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not patient.phone and not patient.email:
        return JSONResponse(
            {"success": True, "message": "No users to notify", "data": {"patient_id": patient.id, "sent": False}}
        )

    try:
        result = await run_in_threadpool(
            send_patient_message,
            patient.phone,
            patient.email,
            "It's been a while. Do you need help or medicines?",
            "Kash AI check-in",
        )
        logger.info("Check-in message sent for patient_id=%s result=%s", patient.id, result)
    except Exception as exc:
        logger.exception("Check-in message failed for patient_id=%s: %s", patient.id, exc)
        result = {"whatsapp": False, "email": False}

    track_event("admin_patient_checkin_sent", doctor_id=doctor.id, patient_id=patient.id, result=result)
    return JSONResponse(
        {
            "success": bool(result.get("whatsapp") or result.get("email")),
            "message": "Check-in message sent" if result.get("whatsapp") or result.get("email") else "No users to notify",
            "data": {"patient_id": patient.id, "result": result},
        }
    )


@router.get("/api/admin/order-health")
@router.get("/admin/order-health")
def order_health_dashboard(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    try:
        failed_payments_count = (
            db.query(func.count(MedicineOrder.id))
            .filter(MedicineOrder.payment_status == "failed")
            .scalar()
            or 0
        )
        whatsapp_failures_count = (
            db.query(func.count(MedicineOrder.id))
            .filter(MedicineOrder.notification_failed.is_(True))
            .scalar()
            or 0
        )
        paid_pending_orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.payment_status == "paid", MedicineOrder.status == "pending")
            .order_by(MedicineOrder.paid_at.asc(), MedicineOrder.id.asc())
            .limit(200)
            .all()
        )
        delayed_orders = [order for order in paid_pending_orders if _medicine_order_is_delayed(order)]
    except Exception as exc:
        logger.exception("Order health dashboard failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Order health could not be loaded.", "data": {}},
        )

    track_event("admin_order_health_viewed", doctor_id=doctor.id)
    return JSONResponse(
        {
            "success": True,
            "message": "Order health loaded.",
            "data": {
                "failed_payments_count": failed_payments_count,
                "delayed_orders_count": len(delayed_orders),
                "whatsapp_failures_count": whatsapp_failures_count,
                "delayed_orders": [
                    {
                        "order_id": order.id,
                        "status": order.status,
                        "payment_status": order.payment_status,
                        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                        "patient_phone": order.patient_phone,
                        "total_amount": order.total_amount,
                    }
                    for order in delayed_orders[:25]
                ],
            },
        }
    )


@router.post("/admin/order/{order_id}/fix")
def fix_medicine_order(
    order_id: int,
    request: Request,
    action: str = Form(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    doctor = _require_admin(doctor)
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    action = action.strip().lower().replace("-", "_")
    before = {
        "status": order.status,
        "payment_status": order.payment_status,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "notification_failed": order.notification_failed,
    }

    if action == "mark_paid":
        order.payment_status = "paid"
        if order.paid_at is None:
            order.paid_at = utc_now()
    elif action == "force_confirm":
        order.payment_status = "paid"
        if order.paid_at is None:
            order.paid_at = utc_now()
        order.status = "confirmed"
    elif action == "reset_status":
        order.status = "pending"
        order.notification_failed = False
    else:
        raise HTTPException(status_code=400, detail="Unsupported fix action.")

    commit_with_retry(db)
    db.refresh(order)
    track_event("admin_order_fixed", doctor_id=doctor.id, order_id=order.id, action=action)
    return JSONResponse(
        {
            "success": True,
            "message": "Order fix applied.",
            "data": {
                "order_id": order.id,
                "action": action,
                "before": before,
                "after": {
                    "status": order.status,
                    "payment_status": order.payment_status,
                    "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                    "notification_failed": order.notification_failed,
                },
            },
        }
    )


@router.get("/api/admin/saas-stats")
def saas_stats(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_doctors = db.query(func.count(Doctor.id)).scalar() or 0
    new_doctors_24h = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_24h
    ).scalar() or 0
    new_doctors_7d = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_7d
    ).scalar() or 0
    new_doctors_30d = db.query(func.count(Doctor.id)).filter(
        Doctor.created_at >= last_30d
    ).scalar() or 0

    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    new_patients_24h = db.query(func.count(Patient.id)).filter(
        Patient.created_at >= last_24h
    ).scalar() or 0

    total_cases = db.query(func.count(CaseSheet.id)).scalar() or 0
    total_appointments = db.query(func.count(Appointment.id)).scalar() or 0

    total_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).scalar() or 0
    active_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.status == "active").scalar() or 0
    trial_clinic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.status == "trial").scalar() or 0
    basic_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.plan_id == "basic").scalar() or 0
    premium_subs = db.query(
        func.count(ClinicSubscription.id)
    ).filter(ClinicSubscription.plan_id == "pro").scalar() or 0

    total_care_plans = db.query(
        func.count(PatientCarePlan.id)
    ).scalar() or 0
    active_care_plans = db.query(
        func.count(PatientCarePlan.id)
    ).filter(PatientCarePlan.status == "active").scalar() or 0

    today = now.date()
    revenue_today = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Payment.status == "paid", Payment.date == today)
        .scalar() or 0
    )
    revenue_7d = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(
            Payment.status == "paid",
            Payment.date >= last_7d.date()
        )
        .scalar() or 0
    )
    revenue_30d = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(
            Payment.status == "paid",
            Payment.date >= last_30d.date()
        )
        .scalar() or 0
    )
    revenue_alltime = float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Payment.status == "paid")
        .scalar() or 0
    )

    daily_signups = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = db.query(func.count(Doctor.id)).filter(
            func.date(Doctor.created_at) == day
        ).scalar() or 0
        daily_signups.append({"date": str(day), "count": count})

    track_event("saas_stats_viewed", doctor_id=doctor.id)
    return JSONResponse({
        "doctors": {
            "total": total_doctors,
            "new_24h": new_doctors_24h,
            "new_7d": new_doctors_7d,
            "new_30d": new_doctors_30d,
            "daily_signups": daily_signups,
        },
        "patients": {
            "total": total_patients,
            "new_24h": new_patients_24h,
        },
        "usage": {
            "total_cases": total_cases,
            "total_appointments": total_appointments,
        },
        "subscriptions": {
            "total": total_clinic_subs,
            "active": active_clinic_subs,
            "trial": trial_clinic_subs,
            "basic": basic_subs,
            "premium": premium_subs,
        },
        "care_plans": {
            "total": total_care_plans,
            "active": active_care_plans,
        },
        "revenue": {
            "today": revenue_today,
            "last_7d": revenue_7d,
            "last_30d": revenue_30d,
            "all_time": revenue_alltime,
        },
    })


@router.post("/api/admin/seed-demo-data")
def seed_demo_data(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    doctor = _require_admin(doctor)
    from models.subscription import ClinicSubscription
    from models.care_plan import PatientCarePlan
    from datetime import datetime, timedelta

    doctors = db.query(Doctor).limit(3).all()
    patients = db.query(Patient).limit(3).all()

    for i, d in enumerate(doctors):
        plans = ["free", "basic", "pro"]
        statuses = ["trial", "active", "active"]
        sub = ClinicSubscription(
            user_id=d.id,
            plan_id=plans[i % 3],
            status=statuses[i % 3],
            started_at=datetime.utcnow() - timedelta(days=30 - i * 5),
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )
        db.add(sub)

    for i, p in enumerate(patients):
        cp = PatientCarePlan(
            patient_id=p.id,
            plan_name=["Basic Detox", "Panchakarma", "Rasayana"][i % 3],
            status=["active", "active", "completed"][i % 3],
            started_at=datetime.utcnow() - timedelta(days=15),
            expires_at=datetime.utcnow() + timedelta(days=45),
        )
        db.add(cp)

    db.commit()
    return JSONResponse({"seeded": True})
