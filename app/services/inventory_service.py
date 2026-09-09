from __future__ import annotations

from threading import Lock
from typing import Any

from app.analytics import log_event
from services import supplier_service
from services.supplier_service import get_supplier_orders, place_supplier_order_safe


_INVENTORY: dict[str, dict[str, int]] = {
    "Paracetamol": {"stock": 100},
    "Ibuprofen": {"stock": 50},
    "Ashwagandha": {"stock": 30},
}
_LOCK = Lock()

_MEDICINE_CATEGORIES: dict[str, str] = {
    "Paracetamol": "tablets",
    "Ibuprofen": "tablets",
    "Ashwagandha": "ayurveda",
}


def get_inventory() -> dict[str, dict[str, int]]:
    try:
        with _LOCK:
            return {name: dict(values) for name, values in _INVENTORY.items()}
    except Exception:
        return {}


def reduce_stock(medicine_name: str, qty: int) -> None:
    try:
        name = str(medicine_name or "").strip()
        quantity = max(int(qty or 0), 0)
        if not name or quantity <= 0:
            return
        with _LOCK:
            if name not in _INVENTORY:
                return
            _INVENTORY[name]["stock"] = max(int(_INVENTORY[name].get("stock", 0)) - quantity, 0)
            stock = _INVENTORY[name]["stock"]
        log_event("inventory_updated", {"medicine_name": name, "stock": stock})
        if stock < 10:
            check_restock(name)
    except Exception:
        return


def get_low_stock(threshold: int = 10) -> dict[str, dict[str, Any]]:
    try:
        limit = int(threshold)
        return {name: values for name, values in get_inventory().items() if int(values.get("stock", 0)) <= limit}
    except Exception:
        return {}


def auto_restock() -> list[dict[str, Any]]:
    try:
        orders: list[dict[str, Any]] = []
        for medicine, values in get_inventory().items():
            if int(values.get("stock", 0)) < 10:
                order = check_restock(medicine)
                if order:
                    orders.append(order)
        return orders
    except Exception:
        return []


def check_restock(medicine_id: str) -> dict[str, Any] | None:
    # SUPPLIER-FULL-1: Low-stock inventory chooses the best active supplier by medicine category.
    try:
        medicine = str(medicine_id or "").strip()
        if not medicine:
            return None
        stock = int(get_inventory().get(medicine, {}).get("stock", 0))
        if stock >= 10:
            return None
        category = _MEDICINE_CATEGORIES.get(medicine, "general")
        supplier = supplier_service.best_supplier_for_category(category)
        if not supplier:
            return None
        order = place_supplier_order_safe(medicine, 50, supplier_id=str(supplier["id"]), category=category)
        log_event(
            "inventory_restock_triggered",
            {"medicine": medicine, "quantity": 50, "supplier_id": supplier["id"], "category": category},
        )
        return order
    except Exception:
        return None


def get_restock_status() -> dict[str, Any]:
    try:
        return {"low_stock": get_low_stock(), "supplier_orders": get_supplier_orders()}
    except Exception:
        return {"low_stock": {}, "supplier_orders": []}
