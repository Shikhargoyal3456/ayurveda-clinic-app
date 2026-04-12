import json
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import track_event
from app.audit import write_audit_event
from app.auth import ensure_csrf_token, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from models.medicine import Medicine, MedicineOrder, Pharmacy
from services import ai_provider, whatsapp


router = APIRouter(tags=["pharmacy"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
logger = logging.getLogger(__name__)


@router.get("/order/{token}", response_class=HTMLResponse)
def patient_order_page(token: str, request: Request):
    return templates.TemplateResponse(
        "patient_order.html",
        {"request": request, "token": token, "csrf_token": ensure_csrf_token(request)},
    )


@router.get("/patient/medicines")
def patient_medicines(db: Session = Depends(get_db)):
    medicines = (
        db.query(Medicine)
        .filter(Medicine.is_available.is_(True))
        .order_by(Medicine.name.asc())
        .all()
    )
    return [
        {
            "id": medicine.id,
            "name": medicine.name,
            "generic_name": medicine.generic_name,
            "category": medicine.category,
            "price": medicine.price,
            "unit": medicine.unit,
            "requires_prescription": medicine.requires_prescription,
            "pharmacy_id": medicine.pharmacy_id,
        }
        for medicine in medicines
    ]


@router.get("/patient/nearby-pharmacies")
async def nearby_pharmacies(lat: float | None = None, lng: float | None = None):
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat and lng are required")

    api_key = settings.google_maps_api_key
    if not api_key:
        logger.warning("Google Maps API key is not configured.")
        return []

    try:
        import requests

        response = await run_in_threadpool(
            requests.get,
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{lat},{lng}",
                "radius": 3000,
                "type": "pharmacy",
                "key": api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        pharmacies = []
        for result in payload.get("results", [])[:10]:
            location = result.get("geometry", {}).get("location", {})
            rating = result.get("rating")
            if rating is not None and rating < 3.5:
                continue

            pharmacies.append(
                {
                    "name": result.get("name", ""),
                    "vicinity": result.get("vicinity", ""),
                    "rating": rating,
                    "lat": location.get("lat"),
                    "lng": location.get("lng"),
                    "place_id": result.get("place_id"),
                    "open_now": result.get("opening_hours", {}).get("open_now"),
                }
            )
        pharmacies.sort(key=lambda item: (item.get("rating") or 0), reverse=True)
        return pharmacies
    except Exception as exc:
        logger.exception("Google Places pharmacy lookup failed: %s", exc)
        return []


@router.post("/patient/ai-suggest")
async def patient_ai_suggest(
    symptoms: str = Form(...),
    _: None = Depends(verify_csrf),
):
    try:
        suggestion, provider = await run_in_threadpool(
            ai_provider.chat_with_fallback,
            "You suggest pharmacy medicine options. Return concise JSON only.",
            f"Suggest medicines for these symptoms:\n{symptoms.strip()}",
            0.2,
        )
        return {"suggestion": suggestion, "provider": provider.value}
    except Exception as exc:
        logger.exception("Pharmacy AI suggestion failed: %s", exc)
        return {"suggestion": "", "error": "AI suggestions are temporarily unavailable."}


@router.post("/patient/order/create")
def create_patient_order(
    request: Request,
    patient_name: str = Form(...),
    patient_phone: str = Form(...),
    patient_address: str = Form(...),
    medicines_json: str = Form(...),
    pharmacy_id: int = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    pharmacy = db.get(Pharmacy, pharmacy_id)
    if pharmacy is None:
        raise HTTPException(status_code=404, detail="Pharmacy not found")

    try:
        items = json.loads(medicines_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid medicines JSON") from exc

    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="Select at least one medicine")

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

    order = MedicineOrder(
        patient_name=patient_name.strip(),
        patient_phone=patient_phone.strip(),
        patient_address=patient_address.strip(),
        medicines_json=json.dumps(normalized_items, ensure_ascii=True),
        total_amount=total_amount,
        status="pending",
        pharmacy_id=pharmacy.id,
        payment_status="pending",
    )
    db.add(order)
    commit_with_retry(db)
    db.refresh(order)

    order.razorpay_order_id = "order_" + str(order.id)
    commit_with_retry(db)
    db.refresh(order)

    write_audit_event("medicine_order_created", request, order_id=order.id, pharmacy_id=pharmacy.id)
    track_event("medicine_order_created", order_id=order.id, pharmacy_id=pharmacy.id, amount=total_amount)
    return {
        "order_id": order.id,
        "amount": total_amount,
        "razorpay_order_id": order.razorpay_order_id,
    }


@router.post("/patient/order/verify")
async def verify_patient_order(
    request: Request,
    order_id: int = Form(...),
    payment_id: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_csrf),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_status == "paid":
        return {"message": "Already paid", "order_id": order.id, "status": order.status}

    order.payment_status = "paid"
    order.status = "confirmed"
    commit_with_retry(db)
    db.refresh(order)

    pharmacy_message = f"New order received\nOrder #{order.id}\nAmount: {order.total_amount}\nAddress: {order.patient_address}"
    patient_message = f"Order confirmed\nOrder #{order.id}\nAmount: {order.total_amount}"
    try:
        await run_in_threadpool(
            whatsapp.send_whatsapp_message,
            order.pharmacy.whatsapp_number or order.pharmacy.phone,
            pharmacy_message,
        )
    except Exception as exc:
        logger.exception("WhatsApp send failed: %s", exc)
    try:
        await run_in_threadpool(
            whatsapp.send_whatsapp_message,
            order.patient_phone,
            patient_message,
        )
    except Exception as exc:
        logger.exception("WhatsApp send failed: %s", exc)

    write_audit_event("medicine_order_payment_verified", request, order_id=order.id, payment_id=payment_id)
    track_event("medicine_order_payment_verified", order_id=order.id, payment_status=order.payment_status)
    return {"order_id": order.id, "status": order.status, "payment_status": order.payment_status}


@router.get("/patient/order/{order_id}/status")
def patient_order_status(order_id: int, db: Session = Depends(get_db)):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_status": order.payment_status,
        "amount": order.total_amount,
    }


@router.get("/pharmacy/dashboard", response_class=HTMLResponse)
def pharmacy_dashboard(request: Request, db: Session = Depends(get_db)):
    orders = db.query(MedicineOrder).order_by(MedicineOrder.created_at.desc()).all()
    return templates.TemplateResponse(
        "pharmacy_portal.html",
        {"request": request, "orders": orders, "csrf_token": ensure_csrf_token(request)},
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
    order.status = "confirmed"
    commit_with_retry(db)
    db.refresh(order)
    write_audit_event("medicine_order_confirmed", request, order_id=order.id, pharmacy_id=order.pharmacy_id)
    track_event("medicine_order_confirmed", order_id=order.id, pharmacy_id=order.pharmacy_id)
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
    order.status = "dispatched"
    commit_with_retry(db)
    db.refresh(order)
    write_audit_event("medicine_order_dispatched", request, order_id=order.id, pharmacy_id=order.pharmacy_id)
    track_event("medicine_order_dispatched", order_id=order.id, pharmacy_id=order.pharmacy_id)
    return RedirectResponse(url="/pharmacy/dashboard", status_code=303)
