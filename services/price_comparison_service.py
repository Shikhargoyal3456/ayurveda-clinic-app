from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from models.marketplace import PharmacyStore
from models.medicine import MasterMedicine, PharmacyInventory


class PriceComparisonService:
    """Compare medicine pricing and identify the best nearby deals."""

    def compare_prices(self, db: Session, medicine_name: str, user_location: dict[str, float]) -> dict[str, Any]:
        medicine = (
            db.query(MasterMedicine)
            .filter(MasterMedicine.is_active.is_(True), MasterMedicine.name.ilike(f"%{str(medicine_name or '').strip()}%"))
            .order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.price.asc())
            .first()
        )
        if medicine is None:
            return {"medicine_name": None, "mrp": None, "pharmacies": [], "best_price": None, "potential_savings": 0, "total_pharmacies": 0}

        rows = (
            db.query(PharmacyInventory, PharmacyStore)
            .join(PharmacyStore, PharmacyStore.id == PharmacyInventory.pharmacy_store_id)
            .filter(
                PharmacyInventory.master_medicine_id == medicine.id,
                PharmacyInventory.is_available.is_(True),
                PharmacyInventory.stock > 0,
            )
            .all()
        )
        comparisons: list[dict[str, Any]] = []
        for inventory, store in rows:
            distance = self.calculate_distance(
                user_location,
                {"lat": float(store.latitude or 0), "lng": float(store.longitude or 0)},
            )
            delivery_fee = self.calculate_delivery_fee(distance)
            medicine_price = float(inventory.clearance_price or inventory.price_override or medicine.price or medicine.mrp or 0)
            total_price = round(medicine_price + delivery_fee, 2)
            comparisons.append(
                {
                    "id": store.id,
                    "pharmacy_name": store.store_name,
                    "medicine_price": round(medicine_price, 2),
                    "delivery_fee": delivery_fee,
                    "total_price": total_price,
                    "distance_km": round(distance, 2),
                    "estimated_delivery_time": self.calculate_eta(distance),
                    "stock_quantity": int(inventory.stock or 0),
                    "pharmacy_rating": float(store.rating or 4.5),
                }
            )
        comparisons.sort(key=lambda item: (item["total_price"], item["distance_km"]))
        cheapest = comparisons[0]["total_price"] if comparisons else None
        most_expensive = comparisons[-1]["total_price"] if len(comparisons) > 1 else cheapest or 0
        potential_savings = round((most_expensive or 0) - (cheapest or 0), 2) if cheapest is not None else 0
        return {
            "medicine_name": medicine.name,
            "mrp": float(medicine.mrp or medicine.price or 0),
            "pharmacies": comparisons,
            "best_price": cheapest,
            "potential_savings": potential_savings,
            "total_pharmacies": len(comparisons),
        }

    def get_best_deals(self, db: Session) -> list[dict[str, Any]]:
        rows = db.query(MasterMedicine).filter(MasterMedicine.is_active.is_(True), MasterMedicine.mrp.is_not(None), MasterMedicine.price.is_not(None)).all()
        deals: list[dict[str, Any]] = []
        for medicine in rows:
            mrp = float(medicine.mrp or 0)
            best_price = float(medicine.price or 0)
            if mrp <= 0 or best_price <= 0 or best_price >= mrp * 0.8:
                continue
            discount_percent = round(((mrp - best_price) / mrp) * 100)
            deals.append(
                {
                    "medicine_name": medicine.name,
                    "mrp": mrp,
                    "best_price": best_price,
                    "discount_percent": discount_percent,
                    "savings": round(mrp - best_price, 2),
                }
            )
        deals.sort(key=lambda item: (item["discount_percent"], item["savings"]), reverse=True)
        return deals[:10]

    def calculate_distance(self, src: dict[str, float], dest: dict[str, float]) -> float:
        lat1 = math.radians(float(src.get("lat", 0) or 0))
        lon1 = math.radians(float(src.get("lng", 0) or 0))
        lat2 = math.radians(float(dest.get("lat", 0) or 0))
        lon2 = math.radians(float(dest.get("lng", 0) or 0))
        d_lat = lat2 - lat1
        d_lon = lon2 - lon1
        a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6371 * c

    def calculate_delivery_fee(self, distance_km: float) -> float:
        if distance_km <= 2:
            return 19.0
        if distance_km <= 5:
            return 29.0
        if distance_km <= 8:
            return 39.0
        return 49.0

    def calculate_eta(self, distance_km: float) -> int:
        return max(15, int(round(distance_km * 8 + 12)))
