from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from models.marketplace import PharmacyStore
from models.medicine import MasterMedicine, MedicineOrder, PharmacyInventory


class PredictiveReorderService:
    """Suggest reorder quantities from recent order patterns."""

    def analyze_sales_pattern(self, db: Session, pharmacy_store_id: int) -> list[dict[str, Any]]:
        store = db.get(PharmacyStore, pharmacy_store_id)
        if store is None:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.pharmacy_id == int(store.source_pharmacy_id or 0), MedicineOrder.created_at >= cutoff.replace(tzinfo=None))
            .all()
        )
        sold_counts: dict[int, int] = defaultdict(int)
        for order in orders:
            try:
                items = json.loads(order.medicines_json or "[]")
            except json.JSONDecodeError:
                items = []
            for item in items if isinstance(items, list) else []:
                medicine_id = int(item.get("master_medicine_id") or item.get("medicine_id") or item.get("id") or 0)
                qty = max(1, int(item.get("qty") or item.get("quantity") or 1))
                if medicine_id:
                    sold_counts[medicine_id] += qty

        suggestions: list[dict[str, Any]] = []
        inventories = db.query(PharmacyInventory).filter(PharmacyInventory.pharmacy_store_id == pharmacy_store_id, PharmacyInventory.is_available.is_(True)).all()
        for inventory in inventories:
            master_id = int(inventory.master_medicine_id or inventory.medicine_id or 0)
            avg_daily_sales = sold_counts.get(master_id, 0) / 30
            if avg_daily_sales <= 0:
                continue
            days_remaining = float(inventory.stock or 0) / avg_daily_sales if avg_daily_sales > 0 else 999
            if days_remaining >= 7:
                continue
            suggested_qty = round(avg_daily_sales * 30)
            medicine = db.get(MasterMedicine, int(inventory.master_medicine_id or 0)) if inventory.master_medicine_id else None
            suggestions.append(
                {
                    "inventory_id": inventory.id,
                    "medicine_id": master_id,
                    "medicine_name": medicine.name if medicine else "Medicine",
                    "current_stock": int(inventory.stock or 0),
                    "avg_daily_sales": round(avg_daily_sales, 2),
                    "days_remaining": round(days_remaining),
                    "suggested_order_qty": suggested_qty,
                    "urgency": "high" if days_remaining < 3 else "medium",
                }
            )
        suggestions.sort(key=lambda item: (item["urgency"] != "high", item["days_remaining"]))
        return suggestions
