import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from threading import Thread
from datetime import timedelta, timezone
from io import BytesIO

try:
    import razorpay
except ImportError:  # pragma: no cover
    razorpay = None
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import log_route_errors, track_error_event, track_event
from app.audit import write_audit_event
from app.auth import ensure_csrf_token, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.portal_auth import get_portal_user
from app.rate_limit import limiter
from app.models import Patient
from models.medicine import MasterMedicine, Medicine, MedicineOrder, MedicineRequest, Pharmacy, utc_now
from services import whatsapp
from services.communication import send_patient_message
from services.delivery_service import assign_delivery_safe, update_delivery_status
from services.email_service import EmailService
from services.fulfillment_service import track_order, update_status
from services.geocoding import get_nearby_pharmacies
from services.inventory_service import reduce_stock
from services.medicine_catalog import get_default_medicines
from services.medicine_management import medicine_request_payload, search_master_medicines
from services.profile_service import profile_avatar_for_relationship, resolve_active_profile
from services.telegram_bot import TelegramOrderNotifier
from services.medicine_api_service import MedicineAPIService
from services.ai_medicine_alternatives import AIMedicineAlternatives
from services.ai_prescription_analyzer import AIPrescriptionAnalyzer
from services.price_comparison_service import PriceComparisonService


router = APIRouter(tags=["pharmacy"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
logger = logging.getLogger(__name__)
client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret)) if razorpay else None
ORDER_AGAIN_SALT = "medicine-order-again"
_PAYMENT_VERIFY_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_FOLLOWUP_SENT_KEYS: set[tuple[int, int]] = set()
_VALID_ORDER_TRANSITIONS = {
    "pending": {"confirmed"},
    "confirmed": {"dispatched"},
    "dispatched": {"delivered"},
    "delivered": set(),
}
email_service = EmailService()
medicine_api_service = MedicineAPIService()
ai_medicine_alternatives = AIMedicineAlternatives()
price_comparison_service = PriceComparisonService()
prescription_analyzer = AIPrescriptionAnalyzer()


def _run_ai_order_processing(order_id: int) -> None:
    try:
        import asyncio

        from services.ai_order_automation import AIOrderAutomation

        asyncio.run(AIOrderAutomation().process_order_with_ai(order_id))
    except Exception as exc:
        logger.warning("AI background order processing failed for order %s: %s", order_id, exc)


def _schedule_ai_order_processing(order_id: int) -> None:
    try:
        Thread(target=_run_ai_order_processing, args=(order_id,), daemon=True, name=f"ai-order-{order_id}").start()
    except Exception as exc:
        logger.warning("AI order processing could not be scheduled for order %s: %s", order_id, exc)


def _order_again_token(order_id: int) -> str:
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=ORDER_AGAIN_SALT)
    return serializer.dumps({"order_id": order_id})


def _load_order_again_token(order_token: str) -> int:
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=ORDER_AGAIN_SALT)
    payload = serializer.loads(order_token, max_age=60 * 60 * 24 * 90)
    return int(payload["order_id"])


def can_transition(current: str, target: str) -> bool:
    return target in _VALID_ORDER_TRANSITIONS.get(current, set())


def _is_ten_digit_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\d{10}", phone.strip()))


def _fallback_razorpay_order_id(order: MedicineOrder) -> str:
    return "order_" + str(order.id)


def _create_razorpay_order_id(order: MedicineOrder, pharmacy: Pharmacy) -> str:
    # PROD-FIX-4: Create a real Razorpay order id instead of only an internal placeholder.
    logger.info("Creating Razorpay order in %s mode: %s", settings.razorpay_mode, order.id)
    if settings.razorpay_mode == "live" and settings.razorpay_key_id.startswith("rzp_test"):
        logger.warning("Razorpay is in live mode but the configured key looks like a test key.")
    if client is None or not settings.razorpay_key_id or not settings.razorpay_key_secret:
        logger.warning("Razorpay unavailable or not configured. Falling back to internal order id for order %s.", order.id)
        return _fallback_razorpay_order_id(order)
    try:
        razorpay_order = client.order.create(
            {
                "amount": int(round(float(order.total_amount or 0) * 100)),
                "currency": "INR",
                "receipt": f"medicine_{order.id}",
                "notes": {
                    "order_id": str(order.id),
                    "pharmacy_id": str(pharmacy.id),
                    "mode": settings.razorpay_mode,
                },
            }
        )
        return str(razorpay_order["id"])
    except Exception as exc:
        logger.exception("Razorpay order creation failed for medicine order %s: %s", order.id, exc)
        track_error_event("payment_order_creation_failure", "/patient/order/create", str(exc), order_id=order.id)
        return _fallback_razorpay_order_id(order)


def _is_order_delayed(order: MedicineOrder) -> bool:
    paid_at = order.paid_at
    if paid_at and paid_at.tzinfo is None:
        paid_at = paid_at.replace(tzinfo=timezone.utc)
    return bool(
        order.payment_status == "paid"
        and order.status == "pending"
        and paid_at
        and utc_now() - paid_at > timedelta(hours=2)
    )


def _order_status_payload(order: MedicineOrder) -> dict[str, object]:
    payment_pending_message = (
        f"Complete your payment to confirm your order: /patient/order/{order.id}/status"
        if order.payment_status == "pending"
        else ""
    )
    return {
        "order_id": order.id,
        "profile_name": order.profile_name,
        "status": order.status,
        "order_status": order.status,
        "payment_status": order.payment_status,
        "payment_pending_message": payment_pending_message,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "is_delayed": _is_order_delayed(order),
        "notification_failed": order.notification_failed,
        "order_again_url": f"/pharmacy/order-again/{_order_again_token(order.id)}",
        "source": _order_source(order),
        "is_repeat_order": _is_repeat_order(order),
    }


def _order_invoice_breakdown(order: MedicineOrder) -> dict[str, object]:
    items = _load_order_items(order)
    subtotal = int(sum(int(item.get("line_total", item.get("price", 0) * item.get("qty", 1)) or 0) for item in items))
    delivery_charge = 0
    discount = max(0, subtotal - int(order.total_amount or 0))
    return {
        "items": items,
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "discount": discount,
        "grand_total": int(order.total_amount or 0),
    }


def _invoice_qr_svg(order: MedicineOrder) -> str:
    verification_payload = f"ORDER:{order.id}|AMOUNT:{order.total_amount}|STATUS:{order.payment_status}"
    try:
        import qrcode
        import qrcode.image.svg

        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(verification_payload, image_factory=factory)
        stream = BytesIO()
        img.save(stream)
        return stream.getvalue().decode("utf-8")
    except Exception:
        return (
            "<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'>"
            "<rect width='180' height='180' fill='#fff7ea' stroke='#2D6A4F' stroke-width='4' rx='20'/>"
            "<text x='90' y='72' font-size='14' text-anchor='middle' fill='#2D6A4F'>Verification Code</text>"
            f"<text x='90' y='98' font-size='16' text-anchor='middle' fill='#1f3d2f'>#{order.id}</text>"
            f"<text x='90' y='126' font-size='12' text-anchor='middle' fill='#5a6a62'>{order.payment_status.upper()}</text>"
            "</svg>"
        )


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    requested_with = request.headers.get("x-requested-with", "")
    return "application/json" in accept.lower() or requested_with.lower() == "xmlhttprequest"


def _payment_rate_limit(request: Request) -> None:
    now = time.time()
    key = f"payment:{request.client.host if request.client else 'unknown'}"
    entries = _PAYMENT_VERIFY_BUCKETS[key]
    while entries and now - entries[0] > 60:
        entries.popleft()
    if len(entries) >= 12:
        raise HTTPException(status_code=429, detail="Too many payment verification attempts. Please wait and retry.")
    entries.append(now)


async def safe_send_whatsapp(phone_number: str | None, message: str, context: str) -> bool:
    try:
        if not phone_number:
            logger.warning("WhatsApp skipped for %s because phone number is missing.", context)
            return False
        await run_in_threadpool(whatsapp.send_whatsapp_message, phone_number, message)
        return True
    except Exception as exc:
        logger.exception("WhatsApp send failed for %s: %s", context, exc)
        return False


def _patient_email_for_order(db: Session, order: MedicineOrder) -> str:
    try:
        patient = (
            db.query(Patient)
            .filter(Patient.phone == order.patient_phone)
            .order_by(Patient.created_at.desc(), Patient.id.desc())
            .first()
        )
        return patient.email if patient and patient.email else ""
    except Exception as exc:
        logger.exception("Patient email lookup failed for order_id=%s: %s", order.id, exc)
        return ""


def _reduce_order_inventory(order: MedicineOrder) -> None:
    try:
        for item in _load_order_items(order):
            if isinstance(item, dict):
                reduce_stock(str(item.get("name") or ""), int(item.get("qty") or 1))
    except Exception as exc:
        logger.exception("Inventory update failed for order_id=%s: %s", order.id, exc)


def _order_followup_anchor(order: MedicineOrder):
    return getattr(order, "updated_at", None) or order.paid_at or order.created_at


def _load_order_items(order: MedicineOrder) -> list[dict[str, object]]:
    try:
        items = json.loads(order.medicines_json or "[]")
    except json.JSONDecodeError:
        logger.exception("Could not parse medicines_json for order_id=%s", order.id)
        return []
    return items if isinstance(items, list) else []


def _followups_sent_for_order(order: MedicineOrder) -> set[str]:
    items = _load_order_items(order)
    if not items or not isinstance(items[0], dict):
        return set()
    raw_sent = items[0].get("followups_sent", [])
    if not isinstance(raw_sent, list):
        return set()
    return {str(item) for item in raw_sent}


def _mark_followup_sent(order: MedicineOrder, followup_key: str) -> None:
    items = _load_order_items(order)
    if not items:
        items = [{}]
    if not isinstance(items[0], dict):
        items.insert(0, {})
    sent = sorted(_followups_sent_for_order(order) | {followup_key})
    items[0]["followups_sent"] = sent
    order.medicines_json = json.dumps(items, ensure_ascii=True)


def _order_source(order: MedicineOrder) -> str:
    items = _load_order_items(order)
    for item in items:
        if isinstance(item, dict):
            source = str(item.get("source", "")).strip().lower()
            if source:
                return source
    return "manual"


def _is_repeat_order(order: MedicineOrder) -> bool:
    for item in _load_order_items(order):
        if isinstance(item, dict) and bool(item.get("is_repeat_order")):
            return True
    return _order_source(order) == "order_again"


def _order_has_followups(order: MedicineOrder) -> bool:
    return bool(_followups_sent_for_order(order))


def _patient_reordered_after(db: Session, order: MedicineOrder, anchor) -> bool:
    try:
        if anchor is None:
            return False
        later_orders = (
            db.query(MedicineOrder)
            .filter(
                MedicineOrder.id != order.id,
                MedicineOrder.patient_phone == order.patient_phone,
                MedicineOrder.created_at > anchor,
            )
            .limit(1)
            .all()
        )
        if later_orders:
            return True
        return (
            db.query(MedicineOrder)
            .filter(MedicineOrder.medicines_json.like(f'%"source_order_id": {order.id}%'))
            .limit(1)
            .first()
            is not None
        )
    except Exception as exc:
        logger.exception("Reorder check failed for order_id=%s: %s", order.id, exc)
        return False


@router.get("/order/{token}", response_class=HTMLResponse)
def patient_order_page(token: str, request: Request):
    return templates.TemplateResponse(
        request,
        "patient_order.html",
        {"request": request, "token": token, "csrf_token": ensure_csrf_token(request)},
    )


@router.get("/pharmacy/order-again/{order_token}", response_class=HTMLResponse)
def order_again_page(order_token: str, request: Request, db: Session = Depends(get_db)):
    try:
        order_id = _load_order_again_token(order_token)
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError) as exc:
        logger.warning("Invalid order-again token: %s", exc)
        raise HTTPException(status_code=404, detail="Order not found") from exc

    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        prefill_medicines = json.loads(order.medicines_json or "[]")
    except json.JSONDecodeError:
        logger.exception("Could not parse medicines_json for order-again order_id=%s", order.id)
        prefill_medicines = []

    return templates.TemplateResponse(
        request,
        "patient_order.html",
        {
            "request": request,
            "token": order_token,
            "csrf_token": ensure_csrf_token(request),
            "prefill_medicines": prefill_medicines if isinstance(prefill_medicines, list) else [],
            "prefill_patient": {
                "name": order.patient_name,
                "phone": order.patient_phone,
                "address": order.patient_address,
            },
            "prefill_order_source": "order_again",
            "prefill_source_order_id": order.id,
        },
    )


@router.get("/patient/medicines")
def patient_medicines(db: Session = Depends(get_db)):
    medicines = (
        db.query(Medicine)
        .filter(Medicine.is_available.is_(True))
        .order_by(Medicine.name.asc())
        .all()
    )
    if not medicines:
        try:
            return [
                {
                    "id": -index,
                    "name": item["name"],
                    "generic_name": item["name"],
                    "category": item["system"],
                    "price": 0,
                    "unit": "catalog",
                    "requires_prescription": not bool(item.get("otc")),
                    "prescription_required": not bool(item.get("otc")),
                    "pharmacy_id": "",
                    "fallback_only": True,
                    "system": item["system"],
                    "otc": bool(item.get("otc")),
                }
                for index, item in enumerate(get_default_medicines(), start=1)
            ]
        except Exception as exc:
            logger.exception("Default medicine catalog fallback failed: %s", exc)
            return []
    return [
        {
            "id": medicine.id,
            "name": medicine.name,
            "generic_name": medicine.generic_name,
            "category": medicine.category,
            "price": medicine.price,
            "unit": medicine.unit,
            "requires_prescription": medicine.requires_prescription,
            "prescription_required": medicine.requires_prescription,
            "pharmacy_id": medicine.pharmacy_id,
        }
        for medicine in medicines
    ]


@router.get("/patient/medicine-alternatives", response_class=HTMLResponse)
def medicine_alternatives_page(request: Request):
    return templates.TemplateResponse(
        request,
        "patient/medicine_alternatives.html",
        {"request": request, "active_page": "medicines", "user_name": "Patient tools", "user_role": "Alternative finder", "avatar_label": "AL"},
    )


@router.get("/patient/price-comparison", response_class=HTMLResponse)
def price_comparison_page(request: Request):
    return templates.TemplateResponse(
        request,
        "patient/price_comparison.html",
        {"request": request, "active_page": "medicines", "user_name": "Patient tools", "user_role": "Price comparison", "avatar_label": "PC"},
    )


@router.get("/api/medicines/search")
def search_medicines(q: str = "", db: Session = Depends(get_db)):
    local = search_master_medicines(db, q, limit=20)
    if local:
        return JSONResponse(
            {
                "medicines": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "brand": item.brand or "",
                        "generic_name": item.generic_name or "",
                        "category": item.category,
                        "price": float(item.price or item.mrp or 0),
                        "mrp": float(item.mrp or item.price or 0),
                        "prescription_required": bool(item.prescription_required),
                        "description": item.description or "",
                    }
                    for item in local
                ]
            }
        )
    return JSONResponse({"medicines": medicine_api_service.search_external_medicines(q)})


@router.get("/api/ai/medicine-alternatives/{medicine_id}")
def medicine_alternatives(medicine_id: int, db: Session = Depends(get_db)):
    source = db.get(MasterMedicine, medicine_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    query = db.query(MasterMedicine).filter(MasterMedicine.id != source.id, MasterMedicine.is_active.is_(True))
    if source.generic_name:
        query = query.filter(MasterMedicine.generic_name == source.generic_name)
    else:
        query = query.filter(MasterMedicine.category == source.category)
    alternatives = query.order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.price.asc()).limit(8).all()
    return JSONResponse(
        {
            "medicine": {"id": source.id, "name": source.name},
            "alternatives": [
                {
                    "id": item.id,
                    "name": item.name,
                    "brand": item.brand or "",
                    "price": float(item.price or item.mrp or 0),
                    "category": item.category,
                }
                for item in alternatives
            ],
        }
    )


@router.get("/api/medicines/alternatives")
def get_alternatives(medicine_name: str = "", db: Session = Depends(get_db)):
    try:
        return JSONResponse(ai_medicine_alternatives.find_alternatives_by_name(db, medicine_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/medicines/compare")
async def compare_prices(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    medicine_name = str(payload.get("medicine_name", "")).strip()
    user_location = payload.get("user_location", {}) if isinstance(payload.get("user_location"), dict) else {}
    return JSONResponse(price_comparison_service.compare_prices(db, medicine_name, user_location))


@router.get("/api/medicines/best-deals")
def get_best_deals(db: Session = Depends(get_db)):
    return JSONResponse(price_comparison_service.get_best_deals(db))


@router.post("/api/patient/request-medicine")
async def request_medicine(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    name = str(payload.get("name", "")).strip()
    brand = str(payload.get("brand", "")).strip() or None
    if not name:
        raise HTTPException(status_code=400, detail="Medicine name is required")
    patient_user = get_portal_user(request, db)
    item = MedicineRequest(
        patient_user_id=int(patient_user.id) if patient_user is not None else None,
        medicine_name=name,
        brand=brand,
        status="pending",
    )
    db.add(item)
    commit_with_retry(db)
    db.refresh(item)
    return JSONResponse({"success": True, "request": medicine_request_payload(item)})


@router.get("/patient/nearby-pharmacies")
@log_route_errors("pharmacy_lookup_failure", "/patient/nearby-pharmacies")
async def nearby_pharmacies(lat: float | None = None, lng: float | None = None):
    if lat is None or lng is None:
        return JSONResponse(status_code=400, content={"success": False, "error": "lat and lng are required", "detail": "lat and lng are required"})
    # GRAND-UNIFIED-1: Use Places API (New) through a cached service with static fallback.
    return await run_in_threadpool(get_nearby_pharmacies, lat, lng)


@router.post("/patient/ai-suggest")
async def patient_ai_suggest(
    symptoms: str = Form(...),
    _: None = Depends(verify_csrf),
):
    try:
        from services import ai_provider

        suggestion, provider = await run_in_threadpool(
            ai_provider.chat_with_fallback,
            "You suggest pharmacy medicine options. Return concise JSON only.",
            f"Suggest medicines for these symptoms:\n{symptoms.strip()}",
            0.2,
            "application/json",
        )
        return {"suggestion": suggestion, "provider": provider.value}
    except Exception as exc:
        logger.exception("Pharmacy AI suggestion failed: %s", exc)
        track_error_event("ai_failure", "/patient/ai-suggest", str(exc))
        return {"suggestion": "", "error": "AI suggestions are temporarily unavailable."}


@router.post("/patient/order/create")
@log_route_errors("order_creation_failure", "/patient/order/create")
@limiter.limit("10/minute")
def create_patient_order(
    request: Request,
    patient_name: str = Form(...),
    patient_phone: str = Form(...),
    patient_address: str = Form(...),
    medicines_json: str = Form(...),
    pharmacy_id: int = Form(...),
    order_source: str = Form(""),
    prescription_id: str = Form(""),
    source_order_id: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    patient_name = patient_name.strip()
    patient_phone = patient_phone.strip()
    patient_address = patient_address.strip()
    if not patient_name or not patient_phone or not patient_address:
        raise HTTPException(status_code=400, detail="Patient name, phone, and address are required")
    if not _is_ten_digit_phone(patient_phone):
        raise HTTPException(status_code=400, detail="Phone number must be 10 digits")

    pharmacy = db.get(Pharmacy, pharmacy_id)
    if pharmacy is None:
        raise HTTPException(status_code=404, detail="Pharmacy not found")

    try:
        items = json.loads(medicines_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid medicines JSON") from exc

    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="Select at least one medicine")

    existing_order_count = (
        db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.patient_phone == patient_phone)
        .scalar()
        or 0
    )
    clean_order_source = order_source.strip().lower()
    if clean_order_source not in {"prescription", "order_again", "followup"}:
        clean_order_source = "manual"
    is_repeat_order = clean_order_source == "order_again" or existing_order_count > 0
    normalized_items = []
    total_amount = 0
    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Invalid medicine item")
        medicine_id = int(item.get("medicine_id") or item.get("id") or 0)
        quantity = int(item.get("qty") or item.get("quantity") or 1)
        if medicine_id <= 0 or quantity <= 0:
            raise HTTPException(status_code=400, detail="Invalid medicine item")

        medicine = (
            db.query(Medicine)
            .filter(
                Medicine.id == medicine_id,
                Medicine.pharmacy_id == pharmacy.id,
                Medicine.is_available.is_(True),
            )
            .first()
        )
        if medicine is None:
            raise HTTPException(status_code=404, detail="Medicine not found")

        line_total = medicine.price * quantity
        total_amount += line_total
        normalized_items.append(
            {
                "medicine_id": medicine.id,
                "name": medicine.name,
                "price": medicine.price,
                "qty": quantity,
                "line_total": line_total,
            }
        )
    parsed_prescription_id = int(prescription_id) if prescription_id.strip().isdigit() else None
    parsed_source_order_id = int(source_order_id) if source_order_id.strip().isdigit() else None
    for normalized_item in normalized_items:
        normalized_item["source"] = clean_order_source
        normalized_item["is_repeat_order"] = is_repeat_order
        if clean_order_source == "prescription" and parsed_prescription_id:
            normalized_item["prescription_id"] = parsed_prescription_id
        if clean_order_source == "order_again" and parsed_source_order_id:
            normalized_item["source_order_id"] = parsed_source_order_id
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="Order amount must be greater than zero")

    portal_user = get_portal_user(request, db)
    active_profile = None
    if portal_user is not None:
        active_profile = resolve_active_profile(request, db, portal_user)
        if active_profile is not None:
            request.session["active_profile_name"] = active_profile.profile_name
            request.session["active_profile_avatar"] = profile_avatar_for_relationship(active_profile.relationship, active_profile.profile_avatar)
            request.session["active_profile_relationship"] = active_profile.relationship

    order = MedicineOrder(
        patient_user_id=int(portal_user.id) if portal_user is not None else None,
        profile_id=int(active_profile.id) if active_profile is not None else None,
        profile_name=active_profile.profile_name if active_profile is not None else None,
        patient_name=patient_name,
        patient_phone=patient_phone,
        patient_address=patient_address,
        medicines_json=json.dumps(normalized_items, ensure_ascii=True),
        total_amount=total_amount,
        status="pending",
        pharmacy_id=pharmacy.id,
        payment_status="pending",
    )
    db.add(order)
    commit_with_retry(db)
    db.refresh(order)

    if clean_order_source == "prescription" and parsed_prescription_id:
        prescription_analyzer.attach_order(db, parsed_prescription_id, order.id)

    order.razorpay_order_id = _create_razorpay_order_id(order, pharmacy)
    commit_with_retry(db)
    db.refresh(order)

    write_audit_event("medicine_order_created", request, order_id=order.id, pharmacy_id=pharmacy.id)
    track_event("medicine_order_created", order_id=order.id, pharmacy_id=pharmacy.id, amount=total_amount)
    track_event("order_created", order_id=order.id, pharmacy_id=pharmacy.id, total=float(total_amount), item_count=len(normalized_items))
    update_status(order.id, "placed")
    assign_delivery_safe(order.id)
    _schedule_ai_order_processing(order.id)
    notifier = TelegramOrderNotifier(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    )
    notifier.send_order_notification(
        {
            "id": order.id,
            "customer_name": order.patient_name,
            "total": order.total_amount,
            "items_count": len(normalized_items),
            "status": order.status,
        }
    )
    patient_email = _patient_email_for_order(db, order)
    if patient_email:
        try:
            import asyncio

            asyncio.create_task(
                email_service.send_order_confirmation(
                    {
                        "id": order.id,
                        "items": normalized_items,
                        "total_amount": order.total_amount,
                    },
                    patient_email,
                )
            )
        except Exception as exc:
            logger.warning("Order confirmation email scheduling failed for order %s: %s", order.id, exc)
    logger.info("Order %s placed for patient phone %s", order.id, order.patient_phone)
    return {
        "order_id": order.id,
        "amount": total_amount,
        "razorpay_order_id": order.razorpay_order_id,
        "status": order.status,
        "order_status": order.status,
        "payment_status": order.payment_status,
        "payment_pending_message": f"Complete your payment to confirm your order: /patient/order/{order.id}/status",
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "order_again_url": f"/pharmacy/order-again/{_order_again_token(order.id)}",
        "source": _order_source(order),
        "is_repeat_order": _is_repeat_order(order),
    }


@router.post("/pharmacy/verify-payment")
@router.post("/patient/order/verify")
@log_route_errors("payment_verification_failure", "/patient/order/verify")
@limiter.limit("10/minute")
async def verify_patient_order(
    request: Request,
    order_id: int = Form(...),
    razorpay_order_id: str | None = Form(None),
    razorpay_payment_id: str | None = Form(None),
    razorpay_signature: str | None = Form(None),
    payment_id: str | None = Form(None),
    db: Session = Depends(get_db),
    __: None = Depends(_payment_rate_limit),
    _: None = Depends(verify_csrf),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    track_event("payment_attempted", order_id=order.id, payment_status=order.payment_status)
    if order.payment_status in {"paid", "failed"}:
        if order.payment_status == "paid" and order.paid_at is None:
            order.paid_at = utc_now()
            commit_with_retry(db)
            db.refresh(order)
        return {
            "message": "Already processed",
            **_order_status_payload(order),
        }

    payment_id_value = razorpay_payment_id or payment_id
    if not razorpay_order_id or not payment_id_value or not razorpay_signature:
        logger.warning("Missing Razorpay payment verification fields for medicine order %s", order.id)
        track_event("payment_failed", order_id=order.id, reason="missing_verification_fields")
        track_error_event("payment_verification_failure", "/patient/order/verify", "Missing Razorpay payment verification fields", order_id=order.id)
        return JSONResponse(
            status_code=400,
            content={"error": "Missing Razorpay payment verification fields", "order_id": order.id},
        )
    if order.razorpay_order_id and order.razorpay_order_id != razorpay_order_id:
        logger.warning(
            "Razorpay order mismatch for medicine order %s: expected=%s received=%s",
            order.id,
            order.razorpay_order_id,
            razorpay_order_id,
        )
        track_event("payment_failed", order_id=order.id, reason="razorpay_order_mismatch")
        track_error_event("payment_verification_failure", "/patient/order/verify", "Razorpay order mismatch", order_id=order.id)
        return JSONResponse(status_code=400, content={"error": "Invalid payment order", "order_id": order.id})
    if client is None:
        logger.error("Razorpay SDK is not installed; payment verification cannot run for medicine order %s", order.id)
        track_event("payment_failed", order_id=order.id, reason="razorpay_sdk_unavailable")
        track_error_event("payment_verification_failure", "/patient/order/verify", "Razorpay SDK is not installed", order_id=order.id)
        return JSONResponse(status_code=503, content={"error": "Payment verification is temporarily unavailable", "order_id": order.id})

    try:
        await run_in_threadpool(
            client.utility.verify_payment_signature,
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": payment_id_value,
                "razorpay_signature": razorpay_signature,
            },
        )
    except Exception as exc:
        logger.exception("Razorpay signature verification failed for medicine order %s: %s", order.id, exc)
        order.payment_status = "failed"
        commit_with_retry(db)
        db.refresh(order)
        track_event("payment_failed", order_id=order.id, reason="signature_verification_failed")
        track_error_event("payment_verification_failure", "/patient/order/verify", str(exc), order_id=order.id)
        return JSONResponse(status_code=400, content={"error": "Payment verification failed", "order_id": order.id})

    order.payment_status = "paid"
    order.status = "pending"
    if order.paid_at is None:
        order.paid_at = utc_now()
    commit_with_retry(db)
    db.refresh(order)

    pharmacy_message = f"New order received\nOrder #{order.id}\nAmount: {order.total_amount}\nAddress: {order.patient_address}"
    patient_message = f"Order confirmed\nOrder #{order.id}\nAmount: {order.total_amount}"
    pharmacy_notified = await safe_send_whatsapp(
        order.pharmacy.whatsapp_number or order.pharmacy.phone,
        pharmacy_message,
        f"pharmacy order {order.id}",
    )
    patient_email = _patient_email_for_order(db, order)
    patient_result = await run_in_threadpool(
        send_patient_message,
        order.patient_phone,
        patient_email,
        # POLISH-8-WHATSAPP-UPDATES: Patient update copy for payment + pharmacy assignment.
        f"Payment received for Order #{order.id}. {order.pharmacy.name} will deliver after pharmacy confirmation.",
        "Kash AI payment successful",
    )
    if not pharmacy_notified or not patient_result.get("whatsapp") or (patient_email and not patient_result.get("email")):
        order.notification_failed = True
        commit_with_retry(db)
        db.refresh(order)
    if patient_email:
        await email_service.send_order_status_update(order.id, "paid", patient_email)

    write_audit_event("medicine_order_payment_verified", request, order_id=order.id, payment_id=payment_id_value)
    _reduce_order_inventory(order)
    update_status(order.id, "packed")
    track_event("medicine_order_payment_verified", order_id=order.id, payment_status=order.payment_status)
    track_event("payment_success", order_id=order.id, total=float(order.total_amount))
    logger.info("Payment verified for order %s", order.id)
    return {
        "message": "Payment successful. Pharmacy will confirm shortly.",
        **_order_status_payload(order),
    }


@router.get("/patient/order/{order_id}/status")
def patient_order_status(order_id: int, db: Session = Depends(get_db)):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order.id,
        "status": order.status,
        "order_status": order.status,
        "payment_status": order.payment_status,
        "payment_pending_message": (
            f"Complete your payment to confirm your order: /patient/order/{order.id}/status"
            if order.payment_status == "pending"
            else ""
        ),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "is_delayed": _is_order_delayed(order),
        "notification_failed": order.notification_failed,
        "amount": order.total_amount,
        "order_again_url": f"/pharmacy/order-again/{_order_again_token(order.id)}",
        "source": _order_source(order),
        "is_repeat_order": _is_repeat_order(order),
    }


@router.get("/order-status/{order_id}")
def public_order_fulfillment_status(order_id: str, db: Session = Depends(get_db)):
    # POLISH-1-ORDER-BUTTONS: Add reorder metadata while preserving the existing fulfillment payload.
    payload = track_order(order_id)
    try:
        numeric_order_id = int(order_id)
        order = db.get(MedicineOrder, numeric_order_id)
        if order is not None:
            payload["order_again_url"] = f"/pharmacy/order-again/{_order_again_token(order.id)}"
            payload["reorder_label"] = "Reorder"
    except Exception as exc:
        logger.exception("Order status reorder metadata failed for order_id=%s: %s", order_id, exc)
    return payload


@router.get("/api/orders/check/{order_id}")
def quick_order_check(order_id: int, db: Session = Depends(get_db)):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        return {"exists": False, "message": "Order not found"}

    created_at = order.created_at.isoformat() if order.created_at else None
    expected_delivery = "Within 24 hours" if order.status in {"pending", "confirmed"} else "On the way"
    if order.status == "delivered":
        expected_delivery = "Delivered"
    elif order.status == "cancelled":
        expected_delivery = "Cancelled"

    return {
        "exists": True,
        "order_id": order.id,
        "status": order.status,
        "total": order.total_amount,
        "placed_at": created_at,
        "expected_delivery": expected_delivery,
        "tracking_url": f"/orders/tracking/{order.id}",
    }


@router.get("/orders/confirmation/{order_id}", response_class=HTMLResponse)
def order_confirmation_page(order_id: int, request: Request, db: Session = Depends(get_db)):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    items = _load_order_items(order)
    subtotal = int(sum(int(item.get("line_total", item.get("price", 0) * item.get("qty", 1)) or 0) for item in items))
    delivery_charge = 0
    discount = max(0, subtotal - int(order.total_amount or 0))
    expected_delivery = "Within 24 hours" if order.status != "delivered" else "Delivered"
    context = {
        "request": request,
        "order": order,
        "active_profile_name": order.profile_name or order.patient_name,
        "order_items": items,
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "discount": discount,
        "expected_delivery": expected_delivery,
        "customer_mobile": order.patient_phone,
        "active_page": "medicines",
        "user_name": order.patient_name,
        "user_role": "Medicine order",
        "avatar_label": "OR",
    }
    return templates.TemplateResponse(request, "orders/confirmation.html", context)


@router.get("/orders/invoice/{order_id}", response_class=HTMLResponse)
def order_invoice_page(order_id: int, request: Request, db: Session = Depends(get_db)):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    breakdown = _order_invoice_breakdown(order)
    context = {
        "request": request,
        "order": order,
        "active_profile_name": order.profile_name or order.patient_name,
        "invoice": breakdown,
        "qr_svg": _invoice_qr_svg(order),
        "active_page": "medicines",
        "user_name": order.patient_name,
        "user_role": "Invoice",
        "avatar_label": "IV",
    }
    return templates.TemplateResponse(request, "orders/invoice.html", context)


@router.get("/pharmacy/dashboard", response_class=HTMLResponse)
def pharmacy_dashboard(request: Request, db: Session = Depends(get_db)):
    orders = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).all()
    for order in orders:
        order.is_delayed = _is_order_delayed(order)
    today = utc_now().date()
    dashboard_metrics = {
        "today_orders_count": db.query(func.count(MedicineOrder.id))
        .filter(func.date(MedicineOrder.created_at) == today.isoformat())
        .scalar()
        or 0,
        "pending_orders_count": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.status == "pending")
        .scalar()
        or 0,
        "revenue_today": db.query(func.coalesce(func.sum(MedicineOrder.total_amount), 0))
        .filter(MedicineOrder.payment_status == "paid", func.date(MedicineOrder.paid_at) == today.isoformat())
        .scalar()
        or 0,
        "failed_payments_count": db.query(func.count(MedicineOrder.id))
        .filter(MedicineOrder.payment_status == "failed")
        .scalar()
        or 0,
    }
    return templates.TemplateResponse(
        request,
        "pharmacy_portal.html",
        {"request": request, "orders": orders, "dashboard_metrics": dashboard_metrics, "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/pharmacy/order/{order_id}/confirm")
def confirm_pharmacy_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status != "paid":
        logger.warning("Medicine order %s confirm blocked because payment_status=%s", order.id, order.payment_status)
        return JSONResponse(status_code=400, content={"error": "Payment must be paid before confirmation"})
    if not can_transition(order.status, "confirmed"):
        logger.warning("Medicine order %s confirm blocked because status=%s", order.id, order.status)
        return JSONResponse(status_code=400, content={"error": "Order must be pending before confirmation"})
    order.status = "confirmed"
    commit_with_retry(db)
    db.refresh(order)
    update_status(order.id, "packed")
    patient_email = _patient_email_for_order(db, order)
    if patient_email:
        try:
            import asyncio

            asyncio.create_task(email_service.send_order_status_update(order.id, "confirmed", patient_email))
        except Exception as exc:
            logger.warning("Confirm email scheduling failed for order %s: %s", order.id, exc)
    write_audit_event("medicine_order_confirmed", request, order_id=order.id, pharmacy_id=order.pharmacy_id)
    track_event("medicine_order_confirmed", order_id=order.id, pharmacy_id=order.pharmacy_id)
    logger.info("Order %s confirmed by pharmacy %s", order.id, order.pharmacy_id)
    if _wants_json(request):
        return JSONResponse({"success": True, "message": "Order confirmed", "data": _order_status_payload(order)})
    return RedirectResponse(url="/pharmacy/dashboard", status_code=303)


@router.post("/pharmacy/order/{order_id}/dispatch")
def dispatch_pharmacy_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_transition(order.status, "dispatched"):
        logger.warning("Medicine order %s dispatch blocked because status=%s", order.id, order.status)
        return JSONResponse(status_code=400, content={"error": "Order must be confirmed before dispatch"})
    order.status = "dispatched"
    commit_with_retry(db)
    db.refresh(order)
    update_status(order.id, "shipped")
    update_delivery_status(order.id, "out_for_delivery")
    patient_email = _patient_email_for_order(db, order)
    if patient_email:
        try:
            import asyncio

            asyncio.create_task(email_service.send_order_status_update(order.id, "dispatched", patient_email))
        except Exception as exc:
            logger.warning("Dispatch email scheduling failed for order %s: %s", order.id, exc)
    write_audit_event("medicine_order_dispatched", request, order_id=order.id, pharmacy_id=order.pharmacy_id)
    track_event("medicine_order_dispatched", order_id=order.id, pharmacy_id=order.pharmacy_id)
    logger.info("Order %s dispatched by pharmacy %s", order.id, order.pharmacy_id)
    if _wants_json(request):
        return JSONResponse(
            {
                "success": True,
                "message": "Pharmacy dispatched your order",
                "data": _order_status_payload(order),
            }
        )
    return RedirectResponse(url="/pharmacy/dashboard", status_code=303)


@router.post("/tasks/run-followups")
def run_followups(db: Session = Depends(get_db)):
    now = utc_now()
    sent: list[dict[str, object]] = []
    skipped = 0
    orders = (
        db.query(MedicineOrder)
        .filter(MedicineOrder.status == "delivered")
        .order_by(MedicineOrder.created_at.desc())
        .limit(500)
        .all()
    )

    for order in orders:
        anchor = _order_followup_anchor(order)
        if anchor is None:
            skipped += 1
            continue
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if _patient_reordered_after(db, order, anchor):
            skipped += 1
            continue
        days_since_delivery = (now - anchor).days
        if days_since_delivery == 3:
            followup_key = "day3"
            message = "How are you feeling after your medicines?"
        elif days_since_delivery == 7:
            followup_key = "day7"
            message = "Time for your follow-up consultation."
        elif days_since_delivery == 14:
            followup_key = "day14"
            message = f"Need help? You can reorder your medicines here: /pharmacy/order-again/{_order_again_token(order.id)}"
        else:
            skipped += 1
            continue

        sent_key = (order.id, days_since_delivery)
        if sent_key in _FOLLOWUP_SENT_KEYS or followup_key in _followups_sent_for_order(order):
            skipped += 1
            continue

        result = send_patient_message(
            order.patient_phone,
            _patient_email_for_order(db, order),
            message,
            subject="Kash AI follow-up",
        )
        _FOLLOWUP_SENT_KEYS.add(sent_key)
        _mark_followup_sent(order, followup_key)
        commit_with_retry(db)
        db.refresh(order)
        sent.append({"order_id": order.id, "day": days_since_delivery, "result": result})

    return JSONResponse({"success": True, "message": "Follow-up sent", "sent": sent, "skipped": skipped})


@router.post("/pharmacy/order/{order_id}/deliver")
def deliver_pharmacy_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_transition(order.status, "delivered"):
        logger.warning("Medicine order %s delivery blocked because status=%s", order.id, order.status)
        return JSONResponse(status_code=400, content={"error": "Order must be dispatched before delivery"})
    order.status = "delivered"
    commit_with_retry(db)
    db.refresh(order)
    update_status(order.id, "delivered")
    update_delivery_status(order.id, "delivered")
    patient_email = _patient_email_for_order(db, order)
    patient_result = send_patient_message(
        order.patient_phone,
        patient_email,
        "Your order has been delivered.",
        subject="Your Kash AI order was delivered",
    )
    if not patient_result.get("whatsapp") or (patient_email and not patient_result.get("email")):
        order.notification_failed = True
        commit_with_retry(db)
        db.refresh(order)
    if patient_email:
        try:
            import asyncio

            asyncio.create_task(email_service.send_order_status_update(order.id, "delivered", patient_email))
        except Exception as exc:
            logger.warning("Delivered email scheduling failed for order %s: %s", order.id, exc)
    write_audit_event("medicine_order_delivered", request, order_id=order.id, pharmacy_id=order.pharmacy_id)
    track_event("medicine_order_delivered", order_id=order.id, pharmacy_id=order.pharmacy_id)
    logger.info("Order %s delivered by pharmacy %s", order.id, order.pharmacy_id)
    if _wants_json(request):
        return JSONResponse(
            {
                "success": True,
                "message": "Your order has been delivered",
                "data": _order_status_payload(order),
            }
        )
    return RedirectResponse(url="/pharmacy/dashboard", status_code=303)
