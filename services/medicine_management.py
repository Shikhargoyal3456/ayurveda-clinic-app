from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import commit_with_retry
from app.portal_auth import parse_float, parse_int
from models.marketplace import PharmacyStore
from models.medicine import MasterMedicine, Medicine, MedicineRequest, Pharmacy, PharmacyInventory, StockAlert
from models.user import PharmacyProfile, User


VALID_MEDICINE_CATEGORIES = {"allopathy", "ayurveda", "homeopathy", "wellness"}
DEFAULT_MEDICINE_IMAGES = {
    "allopathy": "/static/images/medicine-default-allopathy.svg",
    "ayurveda": "/static/images/medicine-default-ayurveda.svg",
    "homeopathy": "/static/images/medicine-default-homeopathy.svg",
    "wellness": "/static/images/medicine-default-wellness.svg",
}


def normalize_category(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in VALID_MEDICINE_CATEGORIES else "wellness"


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_expiry_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def default_image_for_category(category: str) -> str:
    return DEFAULT_MEDICINE_IMAGES.get(normalize_category(category), DEFAULT_MEDICINE_IMAGES["wellness"])


def _normalize_image_list(images: list[str] | None, category: str, fallback_image: str | None = None) -> list[str]:
    normalized = [str(item).strip() for item in (images or []) if str(item).strip()]
    if fallback_image and fallback_image.strip():
        normalized.insert(0, fallback_image.strip())
    deduped: list[str] = []
    for item in normalized:
        if item not in deduped:
            deduped.append(item)
    return deduped or [default_image_for_category(category)]


def parse_images_json(value: str | None, category: str) -> list[str]:
    if not value:
        return [default_image_for_category(category)]
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return [default_image_for_category(category)]
    if not isinstance(payload, list):
        return [default_image_for_category(category)]
    return _normalize_image_list([str(item) for item in payload], category)


def ensure_master_medicine(
    db: Session,
    *,
    name: str,
    category: str,
    brand: str | None = None,
    generic_name: str | None = None,
    mrp: float | None = None,
    price: float | None = None,
    prescription_required: bool = False,
    description: str | None = None,
    image_url: str | None = None,
    barcode: str | None = None,
    manufacturer: str | None = None,
    images: list[str] | None = None,
) -> MasterMedicine:
    clean_name = str(name or "").strip()
    clean_brand = str(brand or "").strip() or None
    if not clean_name:
        raise ValueError("Medicine name is required")
    query = db.query(MasterMedicine).filter(func.lower(MasterMedicine.name) == clean_name.lower())
    if clean_brand:
        query = query.filter(func.lower(func.coalesce(MasterMedicine.brand, "")) == clean_brand.lower())
    medicine = query.first()
    if medicine is None:
        image_list = _normalize_image_list(images, category, image_url)
        medicine = MasterMedicine(
            name=clean_name,
            brand=clean_brand,
            generic_name=str(generic_name or "").strip() or None,
            category=normalize_category(category),
            mrp=mrp,
            price=price,
            prescription_required=bool(prescription_required),
            description=str(description or "").strip() or None,
            image_url=image_list[0],
            images_json=json.dumps(image_list, ensure_ascii=True),
            default_image_url=default_image_for_category(category),
            barcode=str(barcode or "").strip() or None,
            manufacturer=str(manufacturer or "").strip() or None,
            popularity_score=1,
            is_active=True,
        )
        db.add(medicine)
        db.flush()
        return medicine

    if mrp is not None:
        medicine.mrp = mrp
    if price is not None:
        medicine.price = price
    if generic_name:
        medicine.generic_name = str(generic_name).strip()
    if description:
        medicine.description = str(description).strip()
    merged_images = _normalize_image_list(images, category, image_url or medicine.image_url or medicine.default_image_url)
    medicine.image_url = merged_images[0]
    medicine.images_json = json.dumps(merged_images, ensure_ascii=True)
    medicine.default_image_url = default_image_for_category(category)
    if barcode:
        medicine.barcode = str(barcode).strip()
    if manufacturer:
        medicine.manufacturer = str(manufacturer).strip()
    medicine.category = normalize_category(category)
    medicine.prescription_required = bool(prescription_required)
    medicine.popularity_score = int(medicine.popularity_score or 0) + 1
    return medicine


def ensure_pharmacy_store_for_user(db: Session, user: User) -> tuple[PharmacyProfile, PharmacyStore, Pharmacy]:
    profile = db.get(PharmacyProfile, user.id)
    if profile is None:
        raise ValueError("Pharmacy profile not found for this user.")

    store = db.query(PharmacyStore).filter(PharmacyStore.owner_id == user.id).order_by(PharmacyStore.id.asc()).first()
    pharmacy = None
    if store is not None and store.source_pharmacy_id:
        pharmacy = db.get(Pharmacy, int(store.source_pharmacy_id))

    if pharmacy is None:
        pharmacy = Pharmacy(
            name=profile.pharmacy_name or user.full_name or "Marketplace Pharmacy",
            address=profile.address or "Address pending",
            city="Gurugram",
            pincode="122001",
            phone=user.phone,
            whatsapp_number=user.phone,
            lat=str(profile.latitude or "") or None,
            lng=str(profile.longitude or "") or None,
            drug_licence_number=profile.license_number or f"TEMP-LIC-{user.id}",
            is_active=True,
        )
        db.add(pharmacy)
        db.flush()

    if store is None:
        store = PharmacyStore(
            owner_id=user.id,
            source_pharmacy_id=pharmacy.id,
            store_name=profile.pharmacy_name or pharmacy.name,
            address=profile.address or pharmacy.address,
            latitude=str(profile.latitude or pharmacy.lat or "") or None,
            longitude=str(profile.longitude or pharmacy.lng or "") or None,
            phone=user.phone,
            email=user.email,
            gst_number=profile.gst_number or "",
            is_open=bool(profile.is_open),
            delivery_radius_km=int(profile.delivery_radius_km or 5),
            minimum_order_amount=float(profile.minimum_order_amount or 0),
            delivery_fee=49,
            rating=4.5,
            total_orders=0,
        )
        db.add(store)
        db.flush()

    return profile, store, pharmacy


def upsert_pharmacy_inventory_item(
    db: Session,
    *,
    user: User,
    medicine_input: dict[str, Any],
    image_url: str | None = None,
) -> dict[str, Any]:
    profile, store, pharmacy = ensure_pharmacy_store_for_user(db, user)
    input_images = medicine_input.get("images")
    clean_images = [str(item).strip() for item in input_images if str(item).strip()] if isinstance(input_images, list) else []
    master = ensure_master_medicine(
        db,
        name=str(medicine_input.get("name", "")).strip(),
        category=str(medicine_input.get("category", "wellness")),
        brand=str(medicine_input.get("brand", "")).strip() or None,
        generic_name=str(medicine_input.get("generic_name", "")).strip() or None,
        mrp=parse_float(medicine_input.get("mrp")),
        price=parse_float(medicine_input.get("price")),
        prescription_required=normalize_bool(medicine_input.get("prescription_required")),
        description=str(medicine_input.get("description", "")).strip() or None,
        image_url=image_url or str(medicine_input.get("image_url", "")).strip() or None,
        barcode=str(medicine_input.get("barcode", "")).strip() or None,
        manufacturer=str(medicine_input.get("brand", "")).strip() or None,
        images=clean_images,
    )

    name = str(medicine_input.get("name", "")).strip()
    brand = str(medicine_input.get("brand", "")).strip() or None
    operational = (
        db.query(Medicine)
        .filter(
            Medicine.pharmacy_id == pharmacy.id,
            func.lower(Medicine.name) == name.lower(),
            func.lower(func.coalesce(Medicine.brand, "")) == (brand or "").lower(),
        )
        .first()
    )
    stock_value = max(0, int(parse_int(medicine_input.get("stock")) or 0))
    expiry = parse_expiry_date(medicine_input.get("expiry_date"))
    price_value = int(round(parse_float(medicine_input.get("price")) or 0))
    mrp_value = int(round(parse_float(medicine_input.get("mrp")) or price_value))
    if operational is None:
        operational = Medicine(
            name=name,
            generic_name=str(medicine_input.get("generic_name", "")).strip() or None,
            category=normalize_category(str(medicine_input.get("category", "wellness"))),
            price=price_value,
            mrp=mrp_value,
            brand=brand,
            description=str(medicine_input.get("description", "")).strip() or None,
            image_url=(clean_images[0] if clean_images else image_url or str(medicine_input.get("image_url", "")).strip() or master.image_url or default_image_for_category(master.category)),
            stock=stock_value,
            expiry_date=expiry,
            barcode=str(medicine_input.get("barcode", "")).strip() or None,
            unit=str(medicine_input.get("unit", "unit")).strip() or "unit",
            requires_prescription=normalize_bool(medicine_input.get("prescription_required")),
            is_available=stock_value > 0,
            pharmacy_id=pharmacy.id,
            master_medicine_id=master.id,
        )
        db.add(operational)
        db.flush()
    else:
        operational.generic_name = str(medicine_input.get("generic_name", "")).strip() or operational.generic_name
        operational.category = normalize_category(str(medicine_input.get("category", operational.category)))
        operational.price = price_value
        operational.mrp = mrp_value
        operational.brand = brand
        operational.description = str(medicine_input.get("description", "")).strip() or operational.description
        operational.image_url = clean_images[0] if clean_images else image_url or str(medicine_input.get("image_url", "")).strip() or operational.image_url or master.image_url
        operational.stock = stock_value
        operational.expiry_date = expiry
        operational.barcode = str(medicine_input.get("barcode", "")).strip() or operational.barcode
        operational.unit = str(medicine_input.get("unit", operational.unit)).strip() or operational.unit
        operational.requires_prescription = normalize_bool(medicine_input.get("prescription_required"))
        operational.is_available = stock_value > 0
        operational.master_medicine_id = master.id

    inventory = (
        db.query(PharmacyInventory)
        .filter(
            PharmacyInventory.pharmacy_store_id == store.id,
            PharmacyInventory.medicine_id == operational.id,
        )
        .first()
    )
    if inventory is None:
        inventory = PharmacyInventory(
            pharmacy_store_id=store.id,
            pharmacy_user_id=user.id,
            medicine_id=operational.id,
            master_medicine_id=master.id,
            stock=stock_value,
            expiry_date=expiry,
            price_override=parse_float(medicine_input.get("price")),
            barcode=str(medicine_input.get("barcode", "")).strip() or None,
            is_clearance=normalize_bool(medicine_input.get("is_clearance")),
            clearance_price=parse_float(medicine_input.get("clearance_price")),
            clearance_reason=str(medicine_input.get("clearance_reason", "")).strip() or None,
            is_available=stock_value > 0,
        )
        db.add(inventory)
    else:
        inventory.master_medicine_id = master.id
        inventory.stock = stock_value
        inventory.expiry_date = expiry
        inventory.price_override = parse_float(medicine_input.get("price"))
        inventory.barcode = str(medicine_input.get("barcode", "")).strip() or inventory.barcode
        inventory.is_clearance = normalize_bool(medicine_input.get("is_clearance")) if medicine_input.get("is_clearance") is not None else inventory.is_clearance
        inventory.clearance_price = parse_float(medicine_input.get("clearance_price")) if medicine_input.get("clearance_price") not in {None, ""} else inventory.clearance_price
        inventory.clearance_reason = str(medicine_input.get("clearance_reason", "")).strip() or inventory.clearance_reason
        inventory.is_available = stock_value > 0

    commit_with_retry(db)
    db.refresh(master)
    db.refresh(operational)
    db.refresh(inventory)
    return {
        "profile": profile,
        "store": store,
        "pharmacy": pharmacy,
        "master_medicine": master,
        "medicine": operational,
        "inventory": inventory,
    }


def parse_csv_rows(raw_text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(raw_text))
    return [dict(row) for row in reader]


def search_master_medicines(db: Session, query: str, limit: int = 20) -> list[MasterMedicine]:
    clean_query = str(query or "").strip()
    sql = db.query(MasterMedicine).filter(MasterMedicine.is_active.is_(True)).order_by(
        MasterMedicine.popularity_score.desc(),
        MasterMedicine.name.asc(),
    )
    if clean_query:
        like = f"%{clean_query}%"
        sql = sql.filter(
            or_(
                MasterMedicine.name.ilike(like),
                MasterMedicine.brand.ilike(like),
                MasterMedicine.generic_name.ilike(like),
                MasterMedicine.category.ilike(like),
            )
        )
    return sql.limit(max(1, min(limit, 100))).all()


def search_master_by_barcode(db: Session, barcode: str) -> MasterMedicine | None:
    clean = str(barcode or "").strip()
    if not clean:
        return None
    return db.query(MasterMedicine).filter(MasterMedicine.barcode == clean, MasterMedicine.is_active.is_(True)).first()


def medicine_request_payload(item: MedicineRequest) -> dict[str, Any]:
    return {
        "id": item.id,
        "patient_user_id": item.patient_user_id,
        "medicine_name": item.medicine_name,
        "brand": item.brand,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def inventory_payload(item: PharmacyInventory, medicine: Medicine | None, master: MasterMedicine | None) -> dict[str, Any]:
    name = medicine.name if medicine else master.name if master else "Medicine"
    brand = medicine.brand if medicine else master.brand if master else ""
    category = medicine.category if medicine else master.category if master else "wellness"
    price = item.price_override if item.price_override is not None else (
        medicine.price if medicine else master.price if master else 0
    )
    return {
        "id": item.id,
        "medicine_id": item.medicine_id,
        "master_medicine_id": item.master_medicine_id,
        "name": name,
        "brand": brand or "",
        "category": category,
        "stock": int(item.stock or 0),
        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        "price": float(price or 0),
        "mrp": float(medicine.mrp if medicine and medicine.mrp is not None else master.mrp if master and master.mrp is not None else price or 0),
        "barcode": item.barcode or (medicine.barcode if medicine else master.barcode if master else ""),
        "image_url": (medicine.image_url if medicine and medicine.image_url else master.image_url if master and master.image_url else default_image_for_category(category)),
        "images": parse_images_json(master.images_json if master else None, category) if master else [default_image_for_category(category)],
        "is_clearance": bool(item.is_clearance),
        "clearance_price": float(item.clearance_price or 0) if item.clearance_price is not None else None,
        "clearance_reason": item.clearance_reason or "",
        "is_available": bool(item.is_available),
    }


def stock_alert_payload(alert: StockAlert, medicine_name: str = "", brand: str = "") -> dict[str, Any]:
    return {
        "id": alert.id,
        "pharmacy_store_id": alert.pharmacy_store_id,
        "medicine_id": alert.medicine_id,
        "master_medicine_id": alert.master_medicine_id,
        "medicine_name": medicine_name,
        "brand": brand,
        "alert_level": alert.alert_level,
        "current_stock": alert.current_stock,
        "threshold": alert.threshold,
        "is_resolved": bool(alert.is_resolved),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
