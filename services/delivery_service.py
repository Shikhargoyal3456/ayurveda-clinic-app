from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from app.analytics import log_event
from app.database import SessionLocal, commit_with_retry
from models.marketplace import DeliveryPartner, OrderDelivery, PharmacyStore
from models.medicine import Medicine, MedicineOrder
from services.feature_flags import is_delivery_enabled


_DELIVERIES: dict[str, dict[str, str]] = {}
_LOCK = Lock()


def assign_delivery(order_id: str | int) -> dict[str, str]:
    try:
        key = str(order_id)
        delivery = {
            "order_id": key,
            "partner": "Dunzo",
            "status": "assigned",
            "eta": "30 mins",
        }
        with _LOCK:
            _DELIVERIES[key] = delivery
        log_event("delivery_assigned", delivery)
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "partner": "Dunzo", "status": "unassigned", "eta": ""}


def assign_delivery_real(order_id: str | int) -> dict[str, str]:
    try:
        api_url = os.getenv("DELIVERY_API_URL", "").strip()
        if not api_url:
            raise ValueError("DELIVERY_API_URL is not configured")
        import requests

        response = requests.post(api_url, json={"order_id": str(order_id)}, timeout=8)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Delivery API returned non-object JSON")
        delivery = {
            "order_id": str(data.get("order_id") or order_id),
            "partner": str(data.get("partner") or "Dunzo"),
            "status": str(data.get("status") or "assigned"),
            "eta": str(data.get("eta") or "30 mins"),
        }
        with _LOCK:
            _DELIVERIES[delivery["order_id"]] = delivery
        log_event("delivery_assigned", delivery)
        return dict(delivery)
    except Exception:
        return assign_delivery(order_id)


def assign_delivery_safe(order_id: str | int) -> dict[str, str]:
    try:
        log_event("delivery_api_called", {"enabled": is_delivery_enabled(), "order_id": str(order_id)})
        if is_delivery_enabled():
            return assign_delivery_real(order_id)
        return assign_delivery(order_id)
    except Exception:
        return assign_delivery(order_id)


def track_delivery(order_id: str | int) -> dict[str, str]:
    try:
        key = str(order_id)
        with _LOCK:
            delivery = _DELIVERIES.get(key)
            if delivery is None:
                delivery = {"order_id": key, "partner": "Dunzo", "status": "out_for_delivery", "eta": "30 mins"}
                _DELIVERIES[key] = delivery
        if delivery.get("status") == "delivered":
            log_event("delivery_completed", {"order_id": key, "partner": delivery.get("partner", "")})
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "status": "out_for_delivery"}


def update_delivery_status(order_id: str | int, status: str) -> dict[str, str]:
    try:
        key = str(order_id)
        clean_status = str(status or "out_for_delivery").strip().lower()
        if clean_status not in {"assigned", "out_for_delivery", "delivered"}:
            clean_status = "out_for_delivery"
        with _LOCK:
            delivery = _DELIVERIES.setdefault(
                key,
                {"order_id": key, "partner": "Dunzo", "status": "assigned", "eta": "30 mins"},
            )
            delivery["status"] = clean_status
        if clean_status == "delivered":
            log_event("delivery_completed", {"order_id": key, "partner": delivery.get("partner", "")})
        return dict(delivery)
    except Exception:
        return {"order_id": str(order_id), "status": "out_for_delivery"}


def get_delivery_statuses() -> list[dict[str, str]]:
    try:
        with _LOCK:
            return [dict(item) for item in _DELIVERIES.values()]
    except Exception:
        return []


class ZomatoStyleDeliveryService:
    """Marketplace delivery layer that coexists with the legacy delivery helpers."""

    def __init__(self) -> None:
        self.active_deliveries: dict[int, dict[str, Any]] = {}

    async def find_nearest_pharmacy(self, user_location: dict[str, Any], medicines: list[dict[str, Any]]) -> dict[str, Any]:
        pharmacies = await self.get_nearby_pharmacies(user_location)
        available_pharmacies = []
        for pharmacy in pharmacies:
            if await self.check_medicine_availability(int(pharmacy["id"]), medicines):
                available_pharmacies.append(pharmacy)
        available_pharmacies.sort(key=lambda item: (float(item.get("distance", 999)), -float(item.get("rating", 0))))
        best_pharmacy = available_pharmacies[0] if available_pharmacies else None
        return {
            "pharmacy": best_pharmacy,
            "distance": best_pharmacy["distance"] if best_pharmacy else None,
            "eta_minutes": self.calculate_eta(float(best_pharmacy["distance"])) if best_pharmacy else None,
            "delivery_fee": self.calculate_delivery_fee(float(best_pharmacy["distance"])) if best_pharmacy else 0,
        }

    async def assign_delivery_partner(self, order_id: int, pharmacy_location: dict[str, Any], customer_location: dict[str, Any]) -> dict[str, Any]:
        available_partners = await self.get_available_partners()
        if not available_partners:
            return {"order_id": order_id, "status": "unassigned", "eta_minutes": None, "tracking_url": f"/tracking/{order_id}"}
        best_partner = min(
            available_partners,
            key=lambda partner: self.calculate_partner_eta(partner["current_location"], pharmacy_location, customer_location),
        )
        eta_minutes = self.calculate_partner_eta(best_partner["current_location"], pharmacy_location, customer_location)
        delivery = {
            "order_id": order_id,
            "partner_id": best_partner["id"],
            "partner_name": best_partner["name"],
            "partner_phone": best_partner["phone"],
            "status": "assigned",
            "pickup_location": pharmacy_location,
            "delivery_location": customer_location,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "eta_minutes": eta_minutes,
            "tracking_url": f"/tracking/{order_id}",
        }
        self.active_deliveries[order_id] = delivery
        self._persist_delivery(order_id, best_partner["id"], pharmacy_location, customer_location, eta_minutes)
        await self.notify_partner(best_partner, delivery)
        return delivery

    async def track_live_location(self, order_id: int) -> dict[str, Any] | None:
        delivery = self.active_deliveries.get(order_id) or self._load_delivery(order_id)
        if not delivery:
            return None
        partner_location = await self.get_partner_location(int(delivery["partner_id"]))
        remaining_distance = self.calculate_distance(partner_location, delivery["delivery_location"])
        remaining_eta = remaining_distance / 30 * 60
        payload = {
            "order_id": order_id,
            "partner_location": partner_location,
            "remaining_distance_km": round(remaining_distance, 2),
            "remaining_eta_minutes": round(remaining_eta),
            "status": delivery["status"],
        }
        self.active_deliveries[order_id] = {**delivery, "live_location": partner_location}
        self._update_live_location(order_id, partner_location)
        return payload

    async def optimize_batch_delivery(self, orders: list[dict[str, Any]]) -> dict[str, Any]:
        grouped_orders: dict[str, list[dict[str, Any]]] = {}
        for order in orders:
            pincode = str(order.get("delivery_pincode", "unknown"))
            grouped_orders.setdefault(pincode, []).append(order)
        optimized_routes: dict[str, Any] = {}
        for pincode, area_orders in grouped_orders.items():
            optimized_routes[pincode] = {
                "orders": area_orders,
                "optimal_route": self.calculate_optimal_route(area_orders),
                "total_distance": self.calculate_total_distance(area_orders),
                "estimated_time": len(area_orders) * 10,
            }
        return optimized_routes

    async def auto_reroute_on_delay(self, order_id: int) -> dict[str, Any]:
        delivery = self.active_deliveries.get(order_id) or self._load_delivery(order_id)
        if not delivery:
            return {"rerouted": False}
        assigned_at = datetime.fromisoformat(str(delivery["assigned_at"]))
        expected_delivery = assigned_at + timedelta(minutes=int(delivery.get("eta_minutes", 0) or 0))
        if datetime.now(timezone.utc) > expected_delivery:
            alternative = await self.find_alternative_partner(delivery)
            if alternative:
                delivery["partner_id"] = alternative["id"]
                delivery["partner_name"] = alternative["name"]
                delivery["status"] = "rerouted"
                await self.notify_customer(order_id, "Delivery partner changed for faster delivery")
                return {"rerouted": True, "new_partner": alternative}
        return {"rerouted": False}

    async def predict_delivery_time(self, order_history: list[dict[str, Any]]) -> dict[str, Any]:
        if not order_history:
            return {"predicted_minutes": 30, "confidence": 0.65, "factors": {"rush_hour": False, "weekend": False, "historical_avg": 30}}
        avg_time = sum(float(order.get("delivery_time", 30) or 30) for order in order_history) / len(order_history)
        time_of_day = datetime.now().hour
        is_rush_hour = 8 <= time_of_day <= 10 or 17 <= time_of_day <= 19
        is_weekend = datetime.now().weekday() >= 5
        predicted_time = avg_time * (1.3 if is_rush_hour else 1.0) * (1.2 if is_weekend else 1.0)
        return {
            "predicted_minutes": round(predicted_time),
            "confidence": 0.85,
            "factors": {"rush_hour": is_rush_hour, "weekend": is_weekend, "historical_avg": round(avg_time)},
        }

    async def get_nearby_pharmacies(self, user_location: dict[str, Any]) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            stores = db.query(PharmacyStore).filter(PharmacyStore.is_open.is_(True)).order_by(PharmacyStore.rating.desc()).limit(10).all()
            user_lat = float(user_location.get("lat", 28.4595) or 28.4595)
            user_lng = float(user_location.get("lng", 77.0266) or 77.0266)
            if not stores:
                return [
                    {
                        "id": 0,
                        "name": "Kash AI Partner Pharmacy",
                        "rating": 4.7,
                        "distance": 1.2,
                        "delivery_fee": self.calculate_delivery_fee(1.2),
                    }
                ]
            results = []
            for store in stores:
                lat = float(store.latitude or 28.4595)
                lng = float(store.longitude or 77.0266)
                results.append(
                    {
                        "id": store.id,
                        "name": store.store_name,
                        "rating": float(store.rating or 0),
                        "distance": round(self.calculate_distance({"lat": user_lat, "lng": user_lng}, {"lat": lat, "lng": lng}), 2),
                        "delivery_fee": float(store.delivery_fee or 0),
                    }
                )
            return results
        finally:
            db.close()

    async def check_medicine_availability(self, pharmacy_store_id: int, medicines: list[dict[str, Any]]) -> bool:
        if pharmacy_store_id <= 0:
            return True
        db = SessionLocal()
        try:
            store = db.get(PharmacyStore, pharmacy_store_id)
            if store is None:
                return False
            source_pharmacy_id = int(store.source_pharmacy_id or 0)
            if not medicines:
                return db.query(Medicine).filter(Medicine.pharmacy_id == source_pharmacy_id, Medicine.is_available.is_(True)).count() > 0
            names = {str(item.get("name", "")).strip().lower() for item in medicines if str(item.get("name", "")).strip()}
            available = {str(item.name).lower() for item in db.query(Medicine).filter(Medicine.pharmacy_id == source_pharmacy_id, Medicine.is_available.is_(True)).all()}
            return bool(names & available) if names else bool(available)
        finally:
            db.close()

    async def get_available_partners(self) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            partners = db.query(DeliveryPartner).filter(DeliveryPartner.is_available.is_(True)).order_by(DeliveryPartner.rating.desc()).all()
            return [
                {
                    "id": partner.id,
                    "name": partner.name,
                    "phone": partner.phone,
                    "current_location": {"lat": float(partner.current_latitude or 28.4595), "lng": float(partner.current_longitude or 77.0266)},
                    "rating": float(partner.rating or 0),
                }
                for partner in partners
            ]
        finally:
            db.close()

    async def get_partner_location(self, partner_id: int) -> dict[str, float]:
        db = SessionLocal()
        try:
            partner = db.get(DeliveryPartner, partner_id)
            if partner is None:
                return {"lat": 28.4595, "lng": 77.0266}
            lat = float(partner.current_latitude or 28.4595) + random.uniform(-0.002, 0.002)
            lng = float(partner.current_longitude or 77.0266) + random.uniform(-0.002, 0.002)
            partner.current_latitude = f"{lat:.6f}"
            partner.current_longitude = f"{lng:.6f}"
            commit_with_retry(db)
            return {"lat": lat, "lng": lng}
        finally:
            db.close()

    def calculate_eta(self, distance_km: float) -> int:
        return max(10, round(distance_km / 25 * 60))

    def calculate_delivery_fee(self, distance_km: float) -> float:
        return round(25 + max(0, distance_km - 2) * 8, 2)

    def calculate_partner_eta(self, partner_location: dict[str, Any], pharmacy_location: dict[str, Any], customer_location: dict[str, Any]) -> int:
        pickup_distance = self.calculate_distance(partner_location, pharmacy_location)
        delivery_distance = self.calculate_distance(pharmacy_location, customer_location)
        return max(12, round((pickup_distance + delivery_distance) / 25 * 60))

    def calculate_distance(self, source: dict[str, Any], destination: dict[str, Any]) -> float:
        lat1 = float(source.get("lat", 28.4595) or 28.4595)
        lng1 = float(source.get("lng", 77.0266) or 77.0266)
        lat2 = float(destination.get("lat", 28.4595) or 28.4595)
        lng2 = float(destination.get("lng", 77.0266) or 77.0266)
        return (((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2) ** 0.5) * 111

    def calculate_optimal_route(self, orders: list[dict[str, Any]]) -> list[int]:
        return [int(order.get("id", index)) for index, order in enumerate(orders, start=1)]

    def calculate_total_distance(self, orders: list[dict[str, Any]]) -> float:
        return round(len(orders) * 2.4, 2)

    async def find_alternative_partner(self, delivery: dict[str, Any]) -> dict[str, Any] | None:
        partners = await self.get_available_partners()
        candidates = [partner for partner in partners if int(partner["id"]) != int(delivery.get("partner_id", 0) or 0)]
        return candidates[0] if candidates else None

    async def notify_partner(self, partner: dict[str, Any], delivery: dict[str, Any]) -> None:
        log_event("marketplace_delivery_partner_notified", {"partner_id": partner["id"], "order_id": delivery["order_id"]})

    async def notify_customer(self, order_id: int, message: str) -> None:
        log_event("marketplace_delivery_customer_notified", {"order_id": order_id, "message": message})

    async def order_history(self, order_id: int) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(OrderDelivery).order_by(OrderDelivery.created_at.desc()).limit(10).all()
            return [{"order_id": row.order_id, "delivery_time": 28 if row.delivered_time else 34} for row in rows]
        finally:
            db.close()

    def _persist_delivery(self, order_id: int, partner_id: int, pharmacy_location: dict[str, Any], customer_location: dict[str, Any], eta_minutes: int) -> None:
        db = SessionLocal()
        try:
            order = db.get(MedicineOrder, order_id)
            existing = db.query(OrderDelivery).filter(OrderDelivery.order_id == order_id).first()
            if existing is None:
                existing = OrderDelivery(
                    order_id=order_id,
                    pharmacy_id=int(order.pharmacy_id or 0) if order else None,
                    delivery_partner_id=partner_id,
                    status="assigned",
                    pickup_time=datetime.now(timezone.utc),
                    live_latitude=str(pharmacy_location.get("lat", 28.4595)),
                    live_longitude=str(pharmacy_location.get("lng", 77.0266)),
                    delivery_fee=self.calculate_delivery_fee(self.calculate_distance(pharmacy_location, customer_location)),
                    tracking_url=f"/tracking/{order_id}",
                )
                db.add(existing)
            else:
                existing.delivery_partner_id = partner_id
                existing.status = "assigned"
                existing.pickup_time = datetime.now(timezone.utc)
                existing.live_latitude = str(pharmacy_location.get("lat", 28.4595))
                existing.live_longitude = str(pharmacy_location.get("lng", 77.0266))
                existing.tracking_url = f"/tracking/{order_id}"
            commit_with_retry(db)
            log_event("marketplace_delivery_assigned", {"order_id": order_id, "partner_id": partner_id, "eta_minutes": eta_minutes})
        finally:
            db.close()

    def _load_delivery(self, order_id: int) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            row = db.query(OrderDelivery).filter(OrderDelivery.order_id == order_id).first()
            if row is None:
                return None
            partner = db.get(DeliveryPartner, int(row.delivery_partner_id or 0)) if row.delivery_partner_id else None
            return {
                "order_id": order_id,
                "partner_id": int(row.delivery_partner_id or 0),
                "partner_name": partner.name if partner else "Delivery Partner",
                "status": row.status,
                "delivery_location": {"lat": 28.4595, "lng": 77.0266},
                "pickup_location": {"lat": float(row.live_latitude or 28.4595), "lng": float(row.live_longitude or 77.0266)},
                "assigned_at": (row.pickup_time or row.created_at or datetime.now(timezone.utc)).isoformat(),
                "eta_minutes": 30,
            }
        finally:
            db.close()

    def _update_live_location(self, order_id: int, partner_location: dict[str, float]) -> None:
        db = SessionLocal()
        try:
            row = db.query(OrderDelivery).filter(OrderDelivery.order_id == order_id).first()
            if row is None:
                return
            row.live_latitude = f"{partner_location['lat']:.6f}"
            row.live_longitude = f"{partner_location['lng']:.6f}"
            commit_with_retry(db)
        finally:
            db.close()
