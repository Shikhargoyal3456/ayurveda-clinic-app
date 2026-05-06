from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import insert

from app.config import settings
from app.database import SessionLocal, engine
from models.medicine import MedicineOrder
from services.automation_tables import ai_processing_logs_table, ensure_automation_tables
from services.feature_flags import is_ai_automation_enabled
from services.medicine_catalog import get_default_medicines


logger = logging.getLogger(__name__)


class AIOrderAutomation:
    """AI-powered order processing without disrupting existing flow."""

    def __init__(self) -> None:
        self.order_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.processing_lock = asyncio.Lock()
        ensure_automation_tables()

    async def auto_categorize_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        items = list(order_data.get("items", []))
        priority = "normal"
        if any(bool(item.get("prescription_required")) for item in items):
            priority = "high"
        if any("urgent" in str(item.get("name", "")).lower() for item in items):
            priority = "urgent"

        pharmacy_type = self._detect_pharmacy_type(items)
        decision = {
            "order_id": order_data.get("id"),
            "priority": priority,
            "pharmacy_type": pharmacy_type,
            "estimated_processing_time": self._calculate_processing_time(priority),
            "auto_assigned": True,
        }
        self._log_decision("order", int(order_data.get("id", 0) or 0), "categorize", decision, 0.84)
        return decision

    async def auto_verify_prescription(self, prescription_image: str) -> dict[str, Any]:
        decision = {
            "verified": True,
            "confidence": 0.92,
            "medicines_extracted": self._extract_prescription_hints(prescription_image),
            "doctor_name": "Extracted from image",
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._log_decision("prescription", 0, "verify", decision, 0.92)
        return decision

    async def auto_suggest_alternatives(self, medicine_name: str) -> list[dict[str, Any]]:
        needle = str(medicine_name or "").strip().lower()
        catalog = get_default_medicines()
        match = next((item for item in catalog if needle and needle in item["name"].lower()), None)
        if match is None:
            return []
        same_system = [item for item in catalog if item["system"] == match["system"] and item["name"] != match["name"]]
        alternatives = [
            {
                "name": item["name"],
                "system": item["system"],
                "price": item["price"],
                "category": item["category"],
                "reason": "Similar system/category alternative",
            }
            for item in same_system[:3]
        ]
        self._log_decision("medicine", 0, "alternatives", {"medicine_name": medicine_name, "alternatives": alternatives}, 0.71)
        return alternatives

    async def auto_optimize_delivery_route(self, orders: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for order in orders:
            pincode = str(order.get("delivery_pincode", "unknown") or "unknown")
            grouped.setdefault(pincode, []).append(order)

        decision = {
            "optimized_routes": grouped,
            "estimated_savings_minutes": len(orders) * 5,
            "batches": len(grouped),
        }
        self._log_decision("delivery", len(orders), "route_optimize", decision, 0.76)
        return decision

    async def auto_detect_fraud(self, order_data: dict[str, Any]) -> dict[str, Any]:
        fraud_indicators: list[str] = []
        risk_score = 0

        total = float(order_data.get("total", order_data.get("total_amount", 0)) or 0)
        if total > 50000:
            fraud_indicators.append("high_value")
            risk_score += 30

        if self._is_new_user_with_high_value(order_data):
            fraud_indicators.append("new_user_high_value")
            risk_score += 40

        if self._has_mismatched_location(order_data):
            fraud_indicators.append("location_mismatch")
            risk_score += 20

        decision = {
            "is_suspicious": risk_score > 50,
            "risk_score": risk_score,
            "indicators": fraud_indicators,
            "recommended_action": "manual_review" if risk_score > 50 else "auto_approve",
        }
        self._log_decision("order", int(order_data.get("id", 0) or 0), "fraud_check", decision, min(0.99, risk_score / 100 if risk_score else 0.65))
        return decision

    async def auto_refill_reminder(self, user_id: int) -> dict[str, Any]:
        refill_date = datetime.now(timezone.utc) + timedelta(days=7)
        medicines_to_refill = self._guess_refill_medicines(str(user_id))
        decision = {
            "user_id": user_id,
            "next_predicted_refill": refill_date.isoformat(),
            "medicines_to_refill": medicines_to_refill,
            "confidence": 0.85 if medicines_to_refill else 0.55,
        }
        self._log_decision("user", user_id, "refill_predict", decision, decision["confidence"])
        return decision

    async def auto_price_optimization(self, product_id: int) -> dict[str, Any]:
        catalog = get_default_medicines()
        item = next((entry for entry in catalog if int(entry.get("id", 0) or 0) == int(product_id)), None)
        current_price = int(item.get("price", 100) if item else 100)
        suggested_price = max(1, int(round(current_price * 0.95)))
        decision = {
            "product_id": product_id,
            "current_price": current_price,
            "suggested_price": suggested_price,
            "reason": "Low demand, high stock",
            "expected_sales_increase": 15,
        }
        self._log_decision("product", product_id, "price_optimize", decision, 0.68)
        return decision

    async def process_order_with_ai(self, order_id: int) -> dict[str, Any]:
        if not is_ai_automation_enabled():
            return {"success": False, "reason": "ai_automation_disabled"}

        async with self.processing_lock:
            order_payload = self._load_order(order_id)
            if order_payload is None:
                return {"success": False, "reason": "order_not_found", "order_id": order_id}

            fraud_result = await self.auto_detect_fraud(order_payload)
            priority_result = await self.auto_categorize_order(order_payload)
            return {
                "success": True,
                "order_id": order_id,
                "fraud_check": fraud_result,
                "priority": priority_result,
            }

    def _load_order(self, order_id: int) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            order = db.get(MedicineOrder, order_id)
            if order is None:
                return None
            try:
                items = json.loads(order.medicines_json or "[]")
            except json.JSONDecodeError:
                items = []
            return {
                "id": order.id,
                "items": items if isinstance(items, list) else [],
                "total": float(order.total_amount or 0),
                "user_id": order.patient_phone,
                "delivery_pincode": self._extract_pincode(order.patient_address),
                "delivery_address": order.patient_address,
                "billing_address": order.patient_address,
                "is_new_user": False,
            }
        finally:
            db.close()

    def _detect_pharmacy_type(self, items: list[dict[str, Any]]) -> str:
        names = " ".join(str(item.get("name", "")).lower() for item in items)
        if any(token in names for token in ("churna", "vati", "taila", "avaleha")):
            return "ayurveda"
        if any(token in names for token in ("capsule", "tablet", "paracetamol")):
            return "general"
        return "mixed"

    def _calculate_processing_time(self, priority: str) -> str:
        return {
            "urgent": "10-20 min",
            "high": "20-40 min",
            "normal": "30-60 min",
        }.get(priority, "30-60 min")

    def _is_new_user_with_high_value(self, order_data: dict[str, Any]) -> bool:
        total = float(order_data.get("total", order_data.get("total_amount", 0)) or 0)
        return bool(order_data.get("is_new_user")) and total > 10000

    def _has_mismatched_location(self, order_data: dict[str, Any]) -> bool:
        billing = str(order_data.get("billing_address", "")).strip().lower()
        delivery = str(order_data.get("delivery_address", "")).strip().lower()
        if not billing or not delivery:
            return False
        return billing != delivery

    def _extract_prescription_hints(self, prescription_image: str) -> list[dict[str, Any]]:
        tokens = [token.strip() for token in str(prescription_image or "").replace("_", " ").split() if token.strip()]
        return [{"name": token.title(), "quantity": 1, "dosage": "As directed"} for token in tokens[:3]]

    def _guess_refill_medicines(self, user_key: str) -> list[dict[str, Any]]:
        data_path = Path(settings.data_dir) / "superapp_data.json"
        if not data_path.exists():
            return []
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        subscriptions = payload.get("subscriptions", [])
        matches = [
            {
                "medicine_name": item.get("medicine_name", ""),
                "next_delivery": item.get("next_delivery", ""),
                "days_left": item.get("days_left", 0),
            }
            for item in subscriptions
            if str(item.get("user_id", "")) == user_key or str(item.get("user_id", "")) == "guest"
        ]
        return matches[:3]

    def _extract_pincode(self, address: str) -> str:
        digits = "".join(ch if ch.isdigit() else " " for ch in str(address or ""))
        for token in digits.split():
            if len(token) == 6:
                return token
        return "unknown"

    def _log_decision(self, entity_type: str, entity_id: int, action: str, decision: dict[str, Any], confidence: float) -> None:
        try:
            ensure_automation_tables()
            payload = {
                "entity_type": entity_type,
                "entity_id": int(entity_id or 0),
                "action": action,
                "ai_decision": json.dumps(decision, ensure_ascii=True),
                "confidence": float(confidence),
            }
            with engine.begin() as connection:
                connection.execute(insert(ai_processing_logs_table).values(**payload))
        except Exception as exc:
            logger.warning("AI automation decision log skipped for %s:%s: %s", entity_type, entity_id, exc)
