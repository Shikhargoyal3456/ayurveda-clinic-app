from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.auth import ensure_csrf_token
from app.config import settings
from app.database import SessionLocal, commit_with_retry, get_db
from app.portal_auth import require_portal_roles, save_upload, user_public_context
from models.marketplace import PharmacyStore
from models.medicine import MasterMedicine, Medicine, Pharmacy, PharmacyInventory
from models.user import User
from services.ai_image_recognition import AIMedicineImageRecognition
from services.ai_medicine_alternatives import AIMedicineAlternatives
from services.expiry_tracking_service import ExpiryTrackingService
from services.marketplace_service import ensure_marketplace_seed_data, pharmacy_inventory_snapshot, pharmacy_live_orders
from services.medicine_api_service import MedicineAPIService
from services.medicine_management import (
    default_image_for_category,
    ensure_pharmacy_store_for_user,
    inventory_payload,
    normalize_bool,
    parse_csv_rows,
    parse_expiry_date,
    parse_images_json,
    search_master_by_barcode,
    search_master_medicines,
    upsert_pharmacy_inventory_item,
)
from services.predictive_reorder import PredictiveReorderService
from services.price_comparison_service import PriceComparisonService
from services.stock_alert_service import StockAlertService


router = APIRouter(tags=["pharmacy-owner"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
medicine_api_service = MedicineAPIService()
image_recognition_service = AIMedicineImageRecognition()
stock_alert_service = StockAlertService()
expiry_tracking_service = ExpiryTrackingService()
predictive_reorder_service = PredictiveReorderService()
price_comparison_service = PriceComparisonService()
ai_alternatives_service = AIMedicineAlternatives()


class StockAlertConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}

    async def connect(self, store_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(store_id, set()).add(websocket)

    def disconnect(self, store_id: int, websocket: WebSocket) -> None:
        sockets = self.active_connections.get(store_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)
        if sockets and not sockets:
            self.active_connections.pop(store_id, None)

    async def broadcast(self, store_id: int, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.active_connections.get(store_id, set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(store_id, websocket)


stock_alert_manager = StockAlertConnectionManager()


def _inventory_context(request: Request, user: User, **extra) -> dict[str, Any]:
    context = {
        "request": request,
        "active_page": "medicines",
        "csrf_token": ensure_csrf_token(request),
        **user_public_context(user),
    }
    context.update(extra)
    return context


def _store_for_user(db, user: User) -> PharmacyStore:
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    return store


def _inventory_rows_for_user(user: User) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        _, store, _ = ensure_pharmacy_store_for_user(db, user)
        items = (
            db.query(PharmacyInventory, Medicine, MasterMedicine)
            .outerjoin(Medicine, Medicine.id == PharmacyInventory.medicine_id)
            .outerjoin(MasterMedicine, MasterMedicine.id == PharmacyInventory.master_medicine_id)
            .filter(PharmacyInventory.pharmacy_store_id == store.id)
            .order_by(PharmacyInventory.updated_at.desc(), PharmacyInventory.id.desc())
            .all()
        )
        return [inventory_payload(inventory, medicine, master) for inventory, medicine, master in items]
    finally:
        db.close()


def _stock_alerts_for_user(user: User, status: str = "open") -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        store = _store_for_user(db, user)
        return stock_alert_service.list_alerts(db, store.id, status=status)
    finally:
        db.close()


def _expiry_alerts_for_user(user: User) -> tuple[list[dict[str, Any]], dict[str, int]]:
    db = SessionLocal()
    try:
        store = _store_for_user(db, user)
        alerts = expiry_tracking_service.check_expiring_medicines(db, store.id)
        return alerts, expiry_tracking_service.summary(alerts)
    finally:
        db.close()


@router.get("/portal/pharmacy/add-medicine")
def add_medicine_page(request: Request, user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    return templates.TemplateResponse(
        request,
        "pharmacy/add_medicine.html",
        _inventory_context(request, user),
    )


@router.get("/portal/pharmacy/bulk-upload")
def bulk_upload_page(request: Request, user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    return templates.TemplateResponse(
        request,
        "pharmacy/bulk_upload.html",
        _inventory_context(request, user),
    )


@router.get("/portal/pharmacy/stock-alerts")
def stock_alerts_page(request: Request, user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    db = SessionLocal()
    try:
        store = _store_for_user(db, user)
    finally:
        db.close()
    return templates.TemplateResponse(
        request,
        "pharmacy/stock_alerts.html",
        _inventory_context(request, user, pharmacy_id=store.id),
    )


@router.get("/portal/pharmacy/expiry-tracker")
def expiry_tracker_page(request: Request, user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    alerts, summary = _expiry_alerts_for_user(user)
    return templates.TemplateResponse(
        request,
        "pharmacy/expiry_tracker.html",
        _inventory_context(request, user, expiring_medicines=alerts, **summary),
    )


@router.get("/api/pharmacy/inventory")
def get_inventory(user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    return JSONResponse({"inventory": _inventory_rows_for_user(user)})


@router.post("/api/medicines/upload-image")
async def upload_medicine_image(
    image: UploadFile = File(...),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    image_url = save_upload(image, "medicine-images")
    if not image_url:
        raise HTTPException(status_code=400, detail="Unsupported image file.")
    return JSONResponse({"image_url": image_url})


@router.post("/api/medicines/recognize-image")
async def recognize_medicine_image(
    image_url: str = Form(""),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    if not image_url.strip():
        raise HTTPException(status_code=400, detail="image_url is required")
    db = SessionLocal()
    try:
        result = image_recognition_service.identify_medicine_from_image(image_url, db)
    finally:
        db.close()
    return JSONResponse(result)


@router.get("/api/pharmacy/stock-alerts")
def get_stock_alerts(
    status: str = Query(default="open"),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    return JSONResponse(_stock_alerts_for_user(user, status=status))


@router.post("/api/pharmacy/stock-alerts/{alert_id}/resolve")
def resolve_stock_alert(
    alert_id: int,
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    store = _store_for_user(db, user)
    alert = stock_alert_service.mark_resolved(db, alert_id, store.id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return JSONResponse({"success": True, "alert_id": alert.id})


@router.get("/api/pharmacy/expiry-alerts")
def get_expiry_alerts(user: User = Depends(require_portal_roles("pharmacy_owner", "admin"))):
    alerts, summary = _expiry_alerts_for_user(user)
    return JSONResponse({"alerts": alerts, "summary": summary})


@router.post("/api/pharmacy/auto-reorder")
def auto_reorder(
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
):
    db = SessionLocal()
    try:
        store = _store_for_user(db, user)
        suggestions = predictive_reorder_service.analyze_sales_pattern(db, store.id)
    finally:
        db.close()
    return JSONResponse({"ordered_count": len(suggestions), "suggestions": suggestions})


@router.post("/api/pharmacy/medicines/add")
async def add_medicine(
    request: Request,
    name: str = Form(""),
    brand: str = Form(""),
    generic_name: str = Form(""),
    category: str = Form("wellness"),
    mrp: str = Form("0"),
    price: str = Form("0"),
    stock: str = Form("0"),
    expiry_date: str = Form(""),
    prescription_required: str = Form("0"),
    description: str = Form(""),
    unit: str = Form("unit"),
    barcode: str = Form(""),
    image_urls: str = Form("[]"),
    image: UploadFile | None = File(default=None),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    payload: dict[str, Any]
    if "application/json" in request.headers.get("content-type", "").lower():
        payload = await request.json()
    else:
        payload = {
            "name": name,
            "brand": brand,
            "generic_name": generic_name,
            "category": category,
            "mrp": mrp,
            "price": price,
            "stock": stock,
            "expiry_date": expiry_date,
            "prescription_required": prescription_required,
            "description": description,
            "unit": unit,
            "barcode": barcode,
        }
    try:
        payload["images"] = json.loads(image_urls or "[]") if isinstance(image_urls, str) else []
    except json.JSONDecodeError:
        payload["images"] = []

    image_url = save_upload(image, "medicine-images")
    result = upsert_pharmacy_inventory_item(db, user=user, medicine_input=payload, image_url=image_url)
    return JSONResponse(
        {
            "success": True,
            "medicine_id": result["medicine"].id,
            "master_medicine_id": result["master_medicine"].id,
            "inventory_id": result["inventory"].id,
        }
    )


@router.post("/api/pharmacy/medicines/bulk-upload")
async def bulk_upload_medicines(
    file: UploadFile = File(...),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    contents = await file.read()
    rows = parse_csv_rows(contents.decode("utf-8-sig", errors="ignore"))
    added = 0
    failed = 0
    failures: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        try:
            upsert_pharmacy_inventory_item(db, user=user, medicine_input=row, image_url=str(row.get("image_url", "")).strip() or None)
            added += 1
        except Exception as exc:
            failed += 1
            failures.append({"row": index, "error": str(exc)})
    return JSONResponse({"success": True, "added": added, "failed": failed, "failures": failures[:20]})


@router.put("/api/pharmacy/inventory/{inventory_id}/stock")
def update_stock(
    inventory_id: int,
    payload: dict[str, Any] = Body(...),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    inventory = db.get(PharmacyInventory, inventory_id)
    if inventory is None or inventory.pharmacy_store_id != store.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    new_stock = max(0, int(payload.get("stock", 0) or 0))
    inventory.stock = new_stock
    inventory.expiry_date = parse_expiry_date(payload.get("expiry_date")) or inventory.expiry_date
    inventory.is_available = new_stock > 0
    if inventory.medicine_id:
        medicine = db.get(Medicine, inventory.medicine_id)
        if medicine is not None:
            medicine.stock = new_stock
            medicine.expiry_date = inventory.expiry_date
            medicine.is_available = new_stock > 0
    commit_with_retry(db)
    alerts = stock_alert_service.check_inventory(db, store.id)
    if alerts:
        latest = sorted(alerts, key=lambda item: (item["alert_level"] != "critical", item["current_stock"]))[0]
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(stock_alert_manager.broadcast(store.id, latest))
        except RuntimeError:
            pass
    return JSONResponse({"success": True, "inventory_id": inventory.id, "stock": inventory.stock})


@router.post("/api/pharmacy/inventory/{inventory_id}/clearance")
def start_clearance_sale(
    inventory_id: int,
    payload: dict[str, Any] = Body(default={}),
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    inventory = db.get(PharmacyInventory, inventory_id)
    if inventory is None or inventory.pharmacy_store_id != store.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    inventory.is_clearance = True
    inventory.clearance_reason = str(payload.get("reason", "Near Expiry")).strip() or "Near Expiry"
    current_price = float(inventory.price_override or 0)
    discount_percent = float(payload.get("discount_percent", 30) or 30)
    inventory.clearance_price = round(current_price * ((100 - discount_percent) / 100), 2)
    commit_with_retry(db)
    return JSONResponse({"success": True, "inventory_id": inventory.id, "clearance_price": float(inventory.clearance_price or 0)})


@router.post("/api/pharmacy/inventory/{inventory_id}/mark-sold")
def mark_inventory_sold(
    inventory_id: int,
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    inventory = db.get(PharmacyInventory, inventory_id)
    if inventory is None or inventory.pharmacy_store_id != store.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    inventory.stock = 0
    inventory.is_available = False
    inventory.is_clearance = False
    commit_with_retry(db)
    return JSONResponse({"success": True, "inventory_id": inventory.id})


@router.post("/api/pharmacy/inventory/{inventory_id}/return-to-supplier")
def return_inventory_to_supplier(
    inventory_id: int,
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    inventory = db.get(PharmacyInventory, inventory_id)
    if inventory is None or inventory.pharmacy_store_id != store.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    inventory.is_available = False
    inventory.clearance_reason = "Returned to supplier"
    commit_with_retry(db)
    return JSONResponse({"success": True, "inventory_id": inventory.id})


@router.delete("/api/pharmacy/inventory/{inventory_id}")
def delete_inventory_item(
    inventory_id: int,
    user: User = Depends(require_portal_roles("pharmacy_owner", "admin")),
    db=Depends(get_db),
):
    _, store, _ = ensure_pharmacy_store_for_user(db, user)
    inventory = db.get(PharmacyInventory, inventory_id)
    if inventory is None or inventory.pharmacy_store_id != store.id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if inventory.medicine_id:
        medicine = db.get(Medicine, inventory.medicine_id)
        if medicine is not None:
            medicine.is_available = False
            medicine.stock = 0
    inventory.is_available = False
    inventory.stock = 0
    commit_with_retry(db)
    stock_alert_service.check_inventory(db, store.id)
    return JSONResponse({"success": True, "inventory_id": inventory.id})


@router.get("/api/ai/medicine-suggest")
def ai_medicine_suggest(q: str = ""):
    db = SessionLocal()
    try:
        local = [
            {
                "id": item.id,
                "name": item.name,
                "brand": item.brand or item.manufacturer or "",
                "price": float(item.price or item.mrp or 0),
                "category": item.category,
                "description": item.description or "",
                "barcode": item.barcode or "",
                "source": "master",
            }
            for item in search_master_medicines(db, q, limit=10)
        ]
        if local:
            return JSONResponse(local)
    finally:
        db.close()
    return JSONResponse(medicine_api_service.search_external_medicines(q))


@router.get("/api/pharmacy/medicines/barcode/{barcode}")
def barcode_lookup(barcode: str):
    db = SessionLocal()
    try:
        local = search_master_by_barcode(db, barcode)
        if local is not None:
            return JSONResponse(
                {
                    "success": True,
                    "medicine": {
                        "name": local.name,
                        "brand": local.brand or "",
                        "generic_name": local.generic_name or "",
                        "category": local.category,
                        "mrp": float(local.mrp or 0),
                        "price": float(local.price or 0),
                        "description": local.description or "",
                        "barcode": local.barcode or "",
                    },
                }
            )
    finally:
        db.close()
    external = medicine_api_service.import_medicine_by_upc(barcode)
    return JSONResponse({"success": bool(external), "medicine": external})


@router.post("/api/pharmacy/register")
def register_pharmacy_store(payload: dict[str, Any] = Body(...)):
    db = SessionLocal()
    try:
        pharmacy = Pharmacy(
            name=str(payload.get("store_name", "Marketplace Pharmacy")).strip() or "Marketplace Pharmacy",
            address=str(payload.get("address", "")).strip(),
            city=str(payload.get("city", "Gurugram")).strip() or "Gurugram",
            pincode=str(payload.get("pincode", "122001")).strip() or "122001",
            phone=str(payload.get("phone", "9999999999")).strip() or "9999999999",
            whatsapp_number=str(payload.get("phone", "9999999999")).strip() or "9999999999",
            lat=str(payload.get("latitude", "28.4595")),
            lng=str(payload.get("longitude", "77.0266")),
            drug_licence_number=str(payload.get("drug_licence_number", "TEMP-LIC")).strip() or "TEMP-LIC",
            is_active=True,
        )
        db.add(pharmacy)
        commit_with_retry(db)
        db.refresh(pharmacy)
        store = PharmacyStore(
            owner_id=int(payload.get("owner_id", pharmacy.id) or pharmacy.id),
            source_pharmacy_id=pharmacy.id,
            store_name=pharmacy.name,
            address=pharmacy.address,
            latitude=pharmacy.lat,
            longitude=pharmacy.lng,
            phone=pharmacy.phone,
            email=str(payload.get("email", "")).strip(),
            gst_number=str(payload.get("gst_number", "")).strip(),
            is_open=True,
            delivery_radius_km=int(payload.get("delivery_radius_km", 5) or 5),
            minimum_order_amount=float(payload.get("minimum_order_amount", 199) or 199),
            delivery_fee=float(payload.get("delivery_fee", 49) or 49),
            rating=float(payload.get("rating", 4.5) or 4.5),
            total_orders=0,
        )
        db.add(store)
        commit_with_retry(db)
        db.refresh(store)
        return JSONResponse({"success": True, "store_id": store.id, "pharmacy_id": pharmacy.id})
    finally:
        db.close()


@router.get("/api/pharmacy/orders/live")
def get_live_orders(store_id: int = Query(...)):
    ensure_marketplace_seed_data()
    return JSONResponse({"orders": pharmacy_live_orders(store_id)})


@router.put("/api/pharmacy/orders/{order_id}/accept")
def accept_pharmacy_order(order_id: int, payload: dict[str, Any] = Body(default={})):
    db = SessionLocal()
    try:
        from models.medicine import MedicineOrder

        order = db.get(MedicineOrder, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        order.status = "confirmed"
        commit_with_retry(db)
        return JSONResponse({"success": True, "order_id": order.id, "status": order.status, "estimated_prep_time": 18})
    finally:
        db.close()


@router.put("/api/pharmacy/orders/{order_id}/status")
def update_pharmacy_order_status(order_id: int, payload: dict[str, Any] = Body(...)):
    db = SessionLocal()
    try:
        from models.medicine import MedicineOrder

        order = db.get(MedicineOrder, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        order.status = str(payload.get("status", order.status)).strip().lower() or order.status
        commit_with_retry(db)
        return JSONResponse({"success": True, "order_id": order.id, "status": order.status})
    finally:
        db.close()


@router.get("/api/pharmacy/analytics")
def pharmacy_analytics(store_id: int = Query(...)):
    payload = pharmacy_live_orders(store_id)
    completed = [item for item in payload if item["status"] == "delivered"]
    revenue = sum(int(item["total_amount"]) for item in payload)
    return JSONResponse(
        {
            "total_orders": len(payload),
            "completed_orders": len(completed),
            "revenue": revenue,
            "average_order_value": round(revenue / max(1, len(payload)), 2),
        }
    )


@router.post("/api/pharmacy/inventory/bulk")
def bulk_inventory_upload(payload: dict[str, Any] = Body(...)):
    db = SessionLocal()
    try:
        store_id = int(payload.get("store_id", 0) or 0)
        items = payload.get("items", [])
        store = db.get(PharmacyStore, store_id)
        if store is None:
            raise HTTPException(status_code=404, detail="Store not found")
        updated = 0
        from models.user import User as PortalUserModel

        user = db.get(PortalUserModel, int(store.owner_id or 0))
        if user is None:
            raise HTTPException(status_code=404, detail="Owner account not found")
        for item in items if isinstance(items, list) else []:
            upsert_pharmacy_inventory_item(db, user=user, medicine_input=item)
            updated += 1
        return JSONResponse({"success": True, "updated": updated, "inventory": pharmacy_inventory_snapshot(store_id)})
    finally:
        db.close()


@router.websocket("/ws/pharmacy-orders/{store_id}")
async def websocket_pharmacy_orders(websocket: WebSocket, store_id: int):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"orders": pharmacy_live_orders(store_id)})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


@router.websocket("/ws/stock-alerts/{store_id}")
async def websocket_stock_alerts(websocket: WebSocket, store_id: int):
    await stock_alert_manager.connect(store_id, websocket)
    try:
        while True:
            db = SessionLocal()
            try:
                alerts = stock_alert_service.list_alerts(db, store_id, status="open")
            finally:
                db.close()
            await websocket.send_json({"alerts": alerts})
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        stock_alert_manager.disconnect(store_id, websocket)
    except Exception:
        stock_alert_manager.disconnect(store_id, websocket)
