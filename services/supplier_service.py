from __future__ import annotations

import os
import re
from typing import Any
from uuid import uuid4

from app.analytics import log_event
from app.database import SessionLocal, commit_with_retry
from models.supplier import Supplier
from services.feature_flags import is_supplier_enabled


DEFAULT_SUPPLIERS: list[dict[str, Any]] = [
    {
        "id": "sup_1",
        "name": "Pharma Distributor A",
        "phone": "",
        "location": "Delhi",
        "categories": ["general", "tablets", "modern_medicine"],
        "api_url": None,
        "whatsapp": None,
        "is_active": True,
    },
    {
        "id": "sup_2",
        "name": "Ayurveda Supplier B",
        "phone": "",
        "location": "Gurgaon",
        "categories": ["general", "ayurveda", "rare"],
        "api_url": None,
        "whatsapp": None,
        "is_active": True,
    },
]
_SUPPLIER_ORDERS: list[dict[str, Any]] = []


def _normalize_categories(value: object) -> list[str]:
    # SUPPLIER-FULL-1: Accept JSON arrays, comma-separated strings, and repeated form values safely.
    if value is None:
        return ["general"]
    if isinstance(value, str):
        items = re.split(r"[,|]", value)
    elif isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            if isinstance(item, str) and ("," in item or "|" in item):
                items.extend(re.split(r"[,|]", item))
            else:
                items.append(str(item))
    else:
        items = [str(value)]
    categories: list[str] = []
    seen: set[str] = set()
    for item in items:
        category = str(item or "").strip().lower()
        if category and category not in seen:
            seen.add(category)
            categories.append(category)
    return categories or ["general"]


def _supplier_to_dict(supplier: Supplier) -> dict[str, Any]:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "phone": supplier.phone or "",
        "location": supplier.location or "",
        "categories": list(supplier.categories or []),
        "api_url": supplier.api_url or "",
        "whatsapp": supplier.whatsapp or "",
        "is_active": bool(supplier.is_active),
        "created_at": supplier.created_at.isoformat() if supplier.created_at else "",
    }


def _new_supplier_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32]
    return f"sup_{slug or uuid4().hex[:8]}_{uuid4().hex[:6]}"


def seed_default_suppliers() -> None:
    # SUPPLIER-FULL-1: Idempotent DB seed for local startup, tests, and fresh deployments.
    db = SessionLocal()
    try:
        for item in DEFAULT_SUPPLIERS:
            if db.get(Supplier, item["id"]) is not None:
                continue
            db.add(
                Supplier(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    phone=str(item.get("phone") or ""),
                    location=str(item.get("location") or ""),
                    categories=_normalize_categories(item.get("categories")),
                    api_url=item.get("api_url") or None,
                    whatsapp=item.get("whatsapp") or None,
                    is_active=bool(item.get("is_active", True)),
                )
            )
        commit_with_retry(db)
    finally:
        db.close()


def get_all_suppliers(include_inactive: bool = True) -> list[dict[str, Any]]:
    try:
        seed_default_suppliers()
        db = SessionLocal()
        try:
            query = db.query(Supplier)
            if not include_inactive:
                query = query.filter(Supplier.is_active.is_(True))
            return [_supplier_to_dict(item) for item in query.order_by(Supplier.name.asc()).all()]
        finally:
            db.close()
    except Exception:
        return [dict(item) for item in DEFAULT_SUPPLIERS]


def get_suppliers() -> list[dict[str, Any]]:
    # SUPPLIER-FULL-1: Backward-compatible admin commerce helper.
    return get_all_suppliers()


def get_supplier(supplier_id: str) -> dict[str, Any] | None:
    try:
        db = SessionLocal()
        try:
            supplier = db.get(Supplier, str(supplier_id or "").strip())
            return _supplier_to_dict(supplier) if supplier is not None else None
        finally:
            db.close()
    except Exception:
        return None


def create_supplier(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data or {}
    name = str(payload.get("name") or "").strip()
    if not name:
        return {"success": False, "error": "name_required"}
    supplier_id = str(payload.get("id") or "").strip() or _new_supplier_id(name)
    db = SessionLocal()
    try:
        if db.get(Supplier, supplier_id) is not None:
            return {"success": False, "error": "supplier_exists"}
        supplier = Supplier(
            id=supplier_id,
            name=name,
            phone=str(payload.get("phone") or "").strip(),
            location=str(payload.get("location") or "").strip(),
            categories=_normalize_categories(payload.get("categories")),
            api_url=str(payload.get("api_url") or "").strip() or None,
            whatsapp=str(payload.get("whatsapp") or "").strip() or None,
            is_active=bool(payload.get("is_active", True)),
        )
        db.add(supplier)
        commit_with_retry(db)
        db.refresh(supplier)
        result = _supplier_to_dict(supplier)
        log_event("supplier_registered", {"supplier_id": supplier.id, "name": supplier.name})
        return {"success": True, "supplier": result}
    except Exception as exc:
        db.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        db.close()


def update_supplier(supplier_id: str, data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data or {}
    db = SessionLocal()
    try:
        supplier = db.get(Supplier, str(supplier_id or "").strip())
        if supplier is None:
            return {"success": False, "error": "supplier_not_found"}
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                return {"success": False, "error": "name_required"}
            supplier.name = name
        if "phone" in payload:
            supplier.phone = str(payload.get("phone") or "").strip()
        if "location" in payload:
            supplier.location = str(payload.get("location") or "").strip()
        if "categories" in payload:
            supplier.categories = _normalize_categories(payload.get("categories"))
        if "api_url" in payload:
            supplier.api_url = str(payload.get("api_url") or "").strip() or None
        if "whatsapp" in payload:
            supplier.whatsapp = str(payload.get("whatsapp") or "").strip() or None
        if "is_active" in payload:
            value = payload.get("is_active")
            supplier.is_active = value if isinstance(value, bool) else str(value).lower() in {"1", "true", "yes", "on"}
        commit_with_retry(db)
        db.refresh(supplier)
        result = _supplier_to_dict(supplier)
        log_event("supplier_updated", {"supplier_id": supplier.id})
        return {"success": True, "supplier": result}
    except Exception as exc:
        db.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        db.close()


def delete_supplier(supplier_id: str) -> dict[str, Any]:
    # SUPPLIER-FULL-1: Soft-delete suppliers so existing order history remains meaningful.
    db = SessionLocal()
    try:
        supplier = db.get(Supplier, str(supplier_id or "").strip())
        if supplier is None:
            return {"success": False, "error": "supplier_not_found"}
        supplier.is_active = False
        commit_with_retry(db)
        log_event("supplier_deleted", {"supplier_id": supplier.id})
        return {"success": True, "supplier": _supplier_to_dict(supplier)}
    except Exception as exc:
        db.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        db.close()


def best_supplier_for_category(category: str) -> dict[str, Any] | None:
    try:
        wanted = str(category or "general").strip().lower() or "general"
        suppliers = get_all_suppliers(include_inactive=False)
        for supplier in suppliers:
            categories = [str(item).lower() for item in supplier.get("categories", [])]
            if wanted in categories:
                return supplier
        for supplier in suppliers:
            categories = [str(item).lower() for item in supplier.get("categories", [])]
            if "general" in categories:
                return supplier
        return suppliers[0] if suppliers else None
    except Exception:
        return None


def place_supplier_order(medicine_name: str, quantity: int, supplier_id: str | None = None, category: str = "general") -> dict[str, Any]:
    try:
        supplier = get_supplier(supplier_id or "") if supplier_id else best_supplier_for_category(category)
        if supplier is None:
            supplier = DEFAULT_SUPPLIERS[0]
        order = {
            "supplier_id": supplier["id"],
            "supplier_name": supplier.get("name", "Supplier"),
            "medicine": str(medicine_name or "").strip(),
            "quantity": max(int(quantity or 0), 0),
            "status": "ordered",
        }
        _SUPPLIER_ORDERS.append(dict(order))
        log_event("supplier_order_placed", order)
        return dict(order)
    except Exception:
        return {
            "supplier_id": "",
            "supplier_name": "",
            "medicine": str(medicine_name or ""),
            "quantity": 0,
            "status": "failed",
        }


def place_supplier_order_real(medicine: str, qty: int, supplier_id: str | None = None, category: str = "general") -> dict[str, Any]:
    try:
        supplier = get_supplier(supplier_id or "") if supplier_id else best_supplier_for_category(category)
        api_url = (supplier or {}).get("api_url") or os.getenv("SUPPLIER_API_URL", "").strip()
        if not api_url:
            raise ValueError("SUPPLIER_API_URL is not configured")
        import requests

        payload = {"medicine": medicine, "quantity": max(int(qty or 0), 0), "supplier_id": (supplier or {}).get("id")}
        response = requests.post(api_url, json=payload, timeout=8)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Supplier API returned non-object JSON")
        order = {
            "supplier_id": str(data.get("supplier_id") or data.get("id") or (supplier or {}).get("id") or "external_supplier"),
            "supplier_name": str(data.get("supplier_name") or (supplier or {}).get("name") or "External Supplier"),
            "medicine": str(data.get("medicine") or medicine),
            "quantity": int(data.get("quantity") or qty or 0),
            "status": str(data.get("status") or "ordered"),
        }
        _SUPPLIER_ORDERS.append(dict(order))
        return order
    except Exception:
        return place_supplier_order(medicine, qty, supplier_id=supplier_id, category=category)


def place_supplier_order_safe(medicine: str, qty: int, supplier_id: str | None = None, category: str = "general") -> dict[str, Any]:
    try:
        log_event("supplier_api_called", {"enabled": is_supplier_enabled(), "medicine": medicine, "supplier_id": supplier_id or ""})
        if is_supplier_enabled():
            return place_supplier_order_real(medicine, qty, supplier_id=supplier_id, category=category)
        return place_supplier_order(medicine, qty, supplier_id=supplier_id, category=category)
    except Exception:
        return place_supplier_order(medicine, qty, supplier_id=supplier_id, category=category)


def get_supplier_orders() -> list[dict[str, Any]]:
    try:
        return [dict(item) for item in _SUPPLIER_ORDERS]
    except Exception:
        return []
