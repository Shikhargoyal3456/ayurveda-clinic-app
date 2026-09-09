from __future__ import annotations

from datetime import datetime
from typing import Any

from app.database import SessionLocal
from models.marketplace import PharmacyStore
from models.medicine import Medicine


class MarketplaceAI:
    """AI-style heuristics for marketplace routing and pricing."""

    async def route_order_to_best_pharmacy(self, order: dict[str, Any]) -> dict[str, Any]:
        pharmacy_ids = [int(item) for item in order.get("pharmacy_ids", []) if str(item).isdigit()]
        if not pharmacy_ids:
            return {"selected_pharmacy": None, "score": {}, "reason": "No candidate pharmacies supplied"}

        factors = {
            "distance": self.score_distance(order.get("user_location", {})),
            "inventory_match": await self.score_inventory_match(order.get("medicines", []), pharmacy_ids),
            "pharmacy_rating": await self.get_pharmacy_rating(pharmacy_ids),
            "current_load": await self.get_pharmacy_load(pharmacy_ids),
            "price_competitiveness": await self.compare_prices(order.get("medicines", []), pharmacy_ids),
        }
        weights = {"distance": 0.3, "inventory_match": 0.35, "rating": 0.2, "load": 0.1, "price": 0.05}

        best_pharmacy = max(pharmacy_ids, key=lambda pid: self.calculate_score(pid, factors, weights))
        return {
            "selected_pharmacy": best_pharmacy,
            "score": factors,
            "reason": self.get_routing_reason(factors, best_pharmacy),
        }

    async def dynamic_pricing(self, product_id: int, user_context: dict[str, Any]) -> float:
        base_price = await self.get_base_price(product_id)
        demand_score = await self.get_demand_score(product_id)
        demand_multiplier = 1 + (demand_score * 0.1)
        loyalty_discount = await self.get_loyalty_discount(int(user_context.get("user_id", 0) or 0))
        hour = datetime.now().hour
        time_multiplier = 1.2 if 22 <= hour <= 6 else 1.0
        final_price = base_price * demand_multiplier * time_multiplier * (1 - loyalty_discount / 100)
        return round(final_price, 2)

    def score_distance(self, user_location: dict[str, Any]) -> dict[int, float]:
        base = 0.85 if user_location else 0.65
        return {0: base}

    async def score_inventory_match(self, medicines: list[dict[str, Any]], pharmacy_ids: list[int]) -> dict[int, float]:
        db = SessionLocal()
        try:
            results: dict[int, float] = {}
            requested = {str(item.get("name", "")).strip().lower() for item in medicines if str(item.get("name", "")).strip()}
            for pharmacy_id in pharmacy_ids:
                source_pharmacy_id = self._source_pharmacy_id(db, pharmacy_id)
                query = db.query(Medicine).filter(Medicine.pharmacy_id == source_pharmacy_id, Medicine.is_available.is_(True))
                names = {str(item.name).lower() for item in query.all()}
                if not requested:
                    results[pharmacy_id] = 0.7
                elif not names:
                    results[pharmacy_id] = 0.2
                else:
                    results[pharmacy_id] = round(len(requested & names) / max(1, len(requested)), 2)
            return results
        finally:
            db.close()

    async def get_pharmacy_rating(self, pharmacy_ids: list[int]) -> dict[int, float]:
        db = SessionLocal()
        try:
            return {
                store.id: float(store.rating or 0)
                for store in db.query(PharmacyStore).filter(PharmacyStore.id.in_(pharmacy_ids)).all()
            }
        finally:
            db.close()

    async def get_pharmacy_load(self, pharmacy_ids: list[int]) -> dict[int, float]:
        db = SessionLocal()
        try:
            stores = db.query(PharmacyStore).filter(PharmacyStore.id.in_(pharmacy_ids)).all()
            return {store.id: max(0.1, 1 - min(int(store.total_orders or 0) / 100, 0.9)) for store in stores}
        finally:
            db.close()

    async def compare_prices(self, medicines: list[dict[str, Any]], pharmacy_ids: list[int]) -> dict[int, float]:
        db = SessionLocal()
        try:
            scores: dict[int, float] = {}
            for pharmacy_id in pharmacy_ids:
                source_pharmacy_id = self._source_pharmacy_id(db, pharmacy_id)
                rows = db.query(Medicine).filter(Medicine.pharmacy_id == source_pharmacy_id).all()
                if not rows:
                    scores[pharmacy_id] = 0.4
                    continue
                avg = sum(int(row.price or 0) for row in rows) / max(1, len(rows))
                scores[pharmacy_id] = round(max(0.1, 1 - min(avg / 2000, 0.9)), 2)
            return scores
        finally:
            db.close()

    def calculate_score(self, pharmacy_id: int, factors: dict[str, Any], weights: dict[str, float]) -> float:
        distance_score = float(factors.get("distance", {}).get(pharmacy_id, factors.get("distance", {}).get(0, 0.6)))
        inventory_score = float(factors.get("inventory_match", {}).get(pharmacy_id, 0.0))
        rating_score = min(float(factors.get("pharmacy_rating", {}).get(pharmacy_id, 0.0)) / 5, 1.0)
        load_score = float(factors.get("current_load", {}).get(pharmacy_id, 0.5))
        price_score = float(factors.get("price_competitiveness", {}).get(pharmacy_id, 0.5))
        return (
            distance_score * weights["distance"]
            + inventory_score * weights["inventory_match"]
            + rating_score * weights["rating"]
            + load_score * weights["load"]
            + price_score * weights["price"]
        )

    def get_routing_reason(self, factors: dict[str, Any], pharmacy_id: int) -> str:
        inventory = float(factors.get("inventory_match", {}).get(pharmacy_id, 0.0))
        rating = float(factors.get("pharmacy_rating", {}).get(pharmacy_id, 0.0))
        return f"Best combined inventory match ({inventory:.2f}) and rating ({rating:.1f})"

    async def get_base_price(self, product_id: int) -> float:
        db = SessionLocal()
        try:
            product = db.get(Medicine, product_id)
            return float(product.price or 100) if product else 100.0
        finally:
            db.close()

    async def get_demand_score(self, product_id: int) -> float:
        return min(0.8, (product_id % 7) / 10)

    async def get_loyalty_discount(self, user_id: int) -> float:
        return 5.0 if user_id > 0 else 0.0

    def _source_pharmacy_id(self, db: Any, pharmacy_store_id: int) -> int:
        store = db.get(PharmacyStore, pharmacy_store_id)
        return int(store.source_pharmacy_id or 0) if store else 0
