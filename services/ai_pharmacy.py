from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.marketplace import PharmacyStore
from models.medicine import MasterMedicine, Medicine, MedicineOrder, Pharmacy, PharmacyInventory
from services.ai_provider import call_gemini, parse_json_response
from services.cache_service import cache_result


logger = logging.getLogger(__name__)


def _bounded_confidence(value: Any, default: int = 78) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _json_loads(value: str | None) -> list[dict[str, Any]]:
    try:
        payload = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _item_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("medicine_name") or "").strip()


def _item_quantity(item: dict[str, Any]) -> int:
    raw = item.get("qty", item.get("quantity", 1))
    try:
        return max(1, int(raw or 1))
    except (TypeError, ValueError):
        return 1


def _urgency_for_order(order: dict[str, Any]) -> tuple[str, str, int]:
    items = order.get("items", [])
    text_blob = " ".join(
        [
            str(order.get("patient_name") or ""),
            str(order.get("medicines_json") or ""),
            " ".join(_item_name(item) for item in items if isinstance(item, dict)),
        ]
    ).lower()
    has_prescription = bool(order.get("has_prescription"))
    chronic_terms = ["diabetes", "insulin", "bp", "blood pressure", "thyroid", "asthma", "heart", "seizure"]
    urgent_terms = ["fever", "pain", "antibiotic", "infection", "vomit", "emergency"]
    wellness_terms = ["protein", "vitamin", "wellness", "supplement", "skin", "hair"]

    if has_prescription:
        return "high", "Prescription-linked medicines should be packed first.", 90
    if any(term in text_blob for term in chronic_terms):
        return "high", "This order appears tied to chronic-condition continuity.", 86
    if any(term in text_blob for term in urgent_terms):
        return "medium", "The basket suggests short-term symptom relief or acute care demand.", 80
    if any(term in text_blob for term in wellness_terms):
        return "low", "This order looks more wellness-led than clinically urgent.", 72
    return "medium", "Standard medicine fulfillment priority based on available order context.", 75


def build_pharmacy_snapshot(db: Session, pharmacy_store_id: int) -> dict[str, Any] | None:
    store = db.get(PharmacyStore, pharmacy_store_id)
    if store is None:
        return None

    source_pharmacy_id = int(store.source_pharmacy_id or 0)
    pharmacy = db.get(Pharmacy, source_pharmacy_id) if source_pharmacy_id else None
    today = date.today()
    month_ago = today - timedelta(days=30)
    week_ago = today - timedelta(days=7)

    inventory_rows = (
        db.query(PharmacyInventory, Medicine, MasterMedicine)
        .outerjoin(Medicine, Medicine.id == PharmacyInventory.medicine_id)
        .outerjoin(MasterMedicine, MasterMedicine.id == PharmacyInventory.master_medicine_id)
        .filter(PharmacyInventory.pharmacy_store_id == pharmacy_store_id)
        .order_by(PharmacyInventory.updated_at.desc(), PharmacyInventory.id.desc())
        .all()
    )

    product_rows = (
        db.query(Medicine)
        .filter(Medicine.pharmacy_id == source_pharmacy_id)
        .order_by(Medicine.created_at.desc(), Medicine.id.desc())
        .all()
    )
    orders = (
        db.query(MedicineOrder)
        .filter(MedicineOrder.pharmacy_id == source_pharmacy_id)
        .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
        .all()
    )
    recent_orders = [item for item in orders if item.created_at and item.created_at.date() >= month_ago]
    weekly_orders = [item for item in orders if item.created_at and item.created_at.date() >= week_ago]

    inventory_data: list[dict[str, Any]] = []
    inventory_name_to_stock: dict[str, int] = {}
    inventory_name_to_price: dict[str, float] = {}
    for inventory, medicine, master in inventory_rows:
        name = (
            (medicine.name if medicine else None)
            or (master.name if master else None)
            or f"Inventory #{inventory.id}"
        )
        category = (
            (medicine.category if medicine else None)
            or (master.category if master else None)
            or "wellness"
        )
        stock = int(inventory.stock or 0)
        price = float(inventory.clearance_price or inventory.price_override or (medicine.price if medicine else 0) or (master.price if master else 0) or 0)
        inventory_data.append(
            {
                "inventory_id": inventory.id,
                "medicine_id": medicine.id if medicine else None,
                "master_medicine_id": master.id if master else None,
                "name": name,
                "category": category,
                "current_stock": stock,
                "price": round(price, 2),
                "expiry_date": inventory.expiry_date.isoformat() if inventory.expiry_date else None,
                "is_clearance": bool(inventory.is_clearance),
                "is_available": bool(inventory.is_available),
            }
        )
        inventory_name_to_stock[name.lower()] = stock
        inventory_name_to_price[name.lower()] = round(price, 2)

    if not inventory_data:
        for medicine in product_rows:
            inventory_data.append(
                {
                    "inventory_id": medicine.id,
                    "medicine_id": medicine.id,
                    "master_medicine_id": medicine.master_medicine_id,
                    "name": medicine.name,
                    "category": medicine.category,
                    "current_stock": int(medicine.stock or 0),
                    "price": round(float(medicine.price or 0), 2),
                    "expiry_date": medicine.expiry_date.isoformat() if medicine.expiry_date else None,
                    "is_clearance": False,
                    "is_available": bool(medicine.is_available),
                }
            )
            inventory_name_to_stock[medicine.name.lower()] = int(medicine.stock or 0)
            inventory_name_to_price[medicine.name.lower()] = round(float(medicine.price or 0), 2)

    medicine_sales: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "category": "wellness",
            "quantity_30d": 0,
            "quantity_7d": 0,
            "order_count_30d": 0,
            "revenue_30d": 0.0,
            "last_sale_at": None,
        }
    )
    category_counter = Counter()
    customer_spend: dict[str, dict[str, Any]] = defaultdict(lambda: {"name": "", "phone": "", "orders": 0, "spend": 0.0})
    sales_data: list[dict[str, Any]] = []
    prioritized_order_seed: list[dict[str, Any]] = []

    for order in recent_orders:
        items = [item for item in _json_loads(order.medicines_json) if isinstance(item, dict)]
        created_at_iso = order.created_at.isoformat() if order.created_at else None
        sales_data.append(
            {
                "order_id": order.id,
                "created_at": created_at_iso,
                "status": order.status,
                "payment_status": order.payment_status,
                "patient_name": order.patient_name,
                "patient_phone": order.patient_phone,
                "total_amount": float(order.total_amount or 0),
                "items": items,
            }
        )

        customer_key = order.patient_phone or f"order-{order.id}"
        customer_spend[customer_key]["name"] = order.patient_name
        customer_spend[customer_key]["phone"] = order.patient_phone
        customer_spend[customer_key]["orders"] += 1
        customer_spend[customer_key]["spend"] += float(order.total_amount or 0)

        has_prescription = any(str(item.get("source", "")).strip().lower() == "prescription" for item in items)
        order_seed = {
            "order_id": order.id,
            "patient_name": order.patient_name,
            "status": order.status,
            "payment_status": order.payment_status,
            "total_amount": float(order.total_amount or 0),
            "created_at": created_at_iso,
            "items": items,
            "has_prescription": has_prescription,
            "medicines_json": order.medicines_json,
        }
        prioritized_order_seed.append(order_seed)

        for item in items:
            name = _item_name(item)
            if not name:
                continue
            qty = _item_quantity(item)
            category = str(item.get("category") or "").strip().lower()
            if not category:
                inventory_match = next((row for row in inventory_data if row["name"].lower() == name.lower()), None)
                category = str(inventory_match["category"] if inventory_match else "wellness")
            medicine_sales[name.lower()]["name"] = name
            medicine_sales[name.lower()]["category"] = category
            medicine_sales[name.lower()]["quantity_30d"] += qty
            medicine_sales[name.lower()]["order_count_30d"] += 1
            medicine_sales[name.lower()]["revenue_30d"] += float(item.get("price") or 0) * qty
            medicine_sales[name.lower()]["last_sale_at"] = created_at_iso
            category_counter[category] += qty
            if order.created_at and order.created_at.date() >= week_ago:
                medicine_sales[name.lower()]["quantity_7d"] += qty

    top_customers = sorted(
        [
            {
                "customer_name": value["name"] or "Customer",
                "patient_phone": value["phone"],
                "orders_count": value["orders"],
                "total_spend": round(value["spend"], 2),
            }
            for value in customer_spend.values()
        ],
        key=lambda item: (-item["total_spend"], -item["orders_count"]),
    )[:5]

    aggregate = {
        "pharmacy_id": pharmacy_store_id,
        "store_name": store.store_name,
        "source_pharmacy_id": source_pharmacy_id,
        "total_products": len(inventory_data),
        "orders_30d": len(recent_orders),
        "orders_7d": len(weekly_orders),
        "orders_today": len([item for item in orders if item.created_at and item.created_at.date() == today]),
        "revenue_30d": round(sum(float(item.total_amount or 0) for item in recent_orders), 2),
        "revenue_today": round(sum(float(item.total_amount or 0) for item in orders if item.created_at and item.created_at.date() == today), 2),
        "low_stock_count": len([row for row in inventory_data if int(row["current_stock"]) < 10]),
        "clearance_count": len([row for row in inventory_data if row["is_clearance"]]),
        "rating": round(float(store.rating or 0), 2),
        "avg_order_value": round(mean([float(item.total_amount or 0) for item in recent_orders]), 2) if recent_orders else 0,
        "open_orders": len([item for item in orders if str(item.status or "").strip().lower() not in {"delivered", "cancelled"}]),
        "trending_categories": [name for name, _count in category_counter.most_common(4)],
    }
    return {
        "aggregate": aggregate,
        "inventory_data": inventory_data[:80],
        "sales_data": sales_data[:80],
        "medicine_sales": list(medicine_sales.values())[:80],
        "top_customers": top_customers,
        "orders": prioritized_order_seed[:25],
        "price_book": inventory_name_to_price,
        "stock_book": inventory_name_to_stock,
        "pharmacy": pharmacy,
    }


def get_competitor_prices(db: Session, medicine_name: str, source_pharmacy_id: int | None = None) -> list[float]:
    query = db.query(Medicine.price).filter(func.lower(Medicine.name) == str(medicine_name or "").strip().lower())
    if source_pharmacy_id:
        query = query.filter(Medicine.pharmacy_id != int(source_pharmacy_id))
    rows = query.all()
    prices = [round(float(price or 0), 2) for (price,) in rows if price is not None]
    return sorted([price for price in prices if price > 0])[:10]


def _fallback_forecast(snapshot: dict[str, Any]) -> dict[str, Any]:
    aggregate = snapshot["aggregate"]
    medicine_sales = snapshot.get("medicine_sales", [])
    stock_book = snapshot.get("stock_book", {})
    high_demand: list[dict[str, Any]] = []
    low_demand: list[dict[str, Any]] = []
    restock_urgent: list[dict[str, Any]] = []

    for item in medicine_sales:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        current_stock = int(stock_book.get(name.lower(), 0))
        qty_30d = int(item.get("quantity_30d") or 0)
        predicted_sales = max(0, round(qty_30d / 30 * 7))
        days_until_out = round(current_stock / max(qty_30d / 30, 0.2), 1) if qty_30d else 999
        if predicted_sales >= 4:
            high_demand.append(
                {
                    "name": name,
                    "current_stock": current_stock,
                    "predicted_sales": predicted_sales,
                    "days_until_out": days_until_out,
                    "confidence": _bounded_confidence(68 + min(predicted_sales * 2, 24)),
                }
            )
        if current_stock > max(predicted_sales * 2, 10) and int(item.get("quantity_7d") or 0) == 0:
            low_demand.append(
                {
                    "name": name,
                    "current_stock": current_stock,
                    "days_without_sale": 7,
                    "confidence": 72,
                }
            )
        suggested_quantity = max(0, (predicted_sales * 2) - current_stock)
        if suggested_quantity > 0 and days_until_out <= 10:
            restock_urgent.append(
                {
                    "name": name,
                    "suggested_quantity": suggested_quantity,
                    "supplier": "Preferred supplier",
                    "confidence": _bounded_confidence(74 + min(suggested_quantity, 18)),
                }
            )

    if not high_demand and snapshot.get("inventory_data"):
        for row in snapshot["inventory_data"][:3]:
            high_demand.append(
                {
                    "name": row["name"],
                    "current_stock": int(row["current_stock"]),
                    "predicted_sales": max(2, min(6, int(row["current_stock"]) // 3 or 2)),
                    "days_until_out": max(3, int(row["current_stock"]) or 3),
                    "confidence": 65,
                }
            )

    return {
        "high_demand_medicines": high_demand[:5],
        "low_demand_medicines": low_demand[:5],
        "restock_urgent": restock_urgent[:5],
        "trending_categories": aggregate.get("trending_categories", [])[:4],
        "insight": (
            f"{aggregate['orders_7d']} order(s) landed in the last 7 days, and "
            f"{aggregate['low_stock_count']} SKU(s) are already close to a restock threshold."
        ),
        "confidence": _bounded_confidence(76 + min(len(high_demand) * 3, 15)),
    }


def _fallback_customer_insights(snapshot: dict[str, Any]) -> dict[str, Any]:
    medicine_sales = sorted(snapshot.get("medicine_sales", []), key=lambda item: -int(item.get("quantity_7d") or 0))
    top_customers = snapshot.get("top_customers", [])
    trending_medicines = [
        {
            "name": item.get("name"),
            "weekly_units": int(item.get("quantity_7d") or 0),
            "category": item.get("category") or "wellness",
            "confidence": _bounded_confidence(70 + min(int(item.get("quantity_7d") or 0) * 4, 20)),
        }
        for item in medicine_sales[:5]
        if item.get("name")
    ]
    return {
        "trending_medicines": trending_medicines,
        "top_customers": top_customers[:4],
        "customer_signal": (
            f"{len(top_customers)} repeat customer profile(s) are visible from the last 30 days of orders."
            if top_customers
            else "Customer concentration is still low, so watch which families begin repeat ordering first."
        ),
        "confidence": _bounded_confidence(74 + min(len(trending_medicines) * 3, 12)),
    }


def _fallback_pricing_opportunities(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for item in sorted(snapshot.get("medicine_sales", []), key=lambda row: -int(row.get("quantity_7d") or 0))[:4]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        current_price = float(snapshot.get("price_book", {}).get(name.lower(), 0) or 0)
        weekly_demand = int(item.get("quantity_7d") or 0)
        if current_price <= 0:
            continue
        direction = "hold"
        suggested_price = current_price
        if weekly_demand >= 6:
            direction = "lift"
            suggested_price = round(current_price * 1.03, 2)
        elif weekly_demand <= 1:
            direction = "discount"
            suggested_price = round(current_price * 0.97, 2)
        opportunities.append(
            {
                "medicine_name": name,
                "current_price": round(current_price, 2),
                "suggested_price": round(suggested_price, 2),
                "change_percent": round(((suggested_price - current_price) / current_price) * 100, 2) if current_price else 0,
                "expected_sales_impact": "stable" if direction == "hold" else ("increase" if direction == "discount" else "controlled"),
                "confidence": _bounded_confidence(68 + min(weekly_demand * 4, 22)),
            }
        )
    return opportunities


def _fallback_daily_insights(snapshot: dict[str, Any]) -> dict[str, Any]:
    aggregate = snapshot["aggregate"]
    customer_insights = _fallback_customer_insights(snapshot)
    pricing_opportunities = _fallback_pricing_opportunities(snapshot)
    if aggregate["low_stock_count"] >= 5:
        focus_area = "inventory"
        tip = "Clear the low-stock list before the evening demand spike starts."
        alert = f"{aggregate['low_stock_count']} SKU(s) are below comfortable operating stock."
    elif aggregate["orders_today"] >= 8:
        focus_area = "service"
        tip = "Keep high-value and prescription-led orders moving first to protect ratings."
        alert = ""
    else:
        focus_area = "marketing"
        tip = "Use slower hours to review repeat customers and refill opportunities."
        alert = ""

    return {
        "tip": tip,
        "focus_area": focus_area,
        "alert": alert,
        "opportunity": (
            "Push refill reminders for repeat buyers and diabetes / BP continuity baskets."
            if customer_insights.get("top_customers")
            else "Trend the fastest-moving medicines and convert those into same-day refill prompts."
        ),
        "message": (
            f"Today starts with {aggregate['orders_today']} order(s), Rs {aggregate['revenue_today']:.0f} in revenue so far, "
            f"and {aggregate['low_stock_count']} inventory alert(s) worth watching."
        ),
        "customer_insights": customer_insights,
        "pricing_opportunities": pricing_opportunities,
        "confidence": _bounded_confidence(77 + min(len(pricing_opportunities) * 2, 10)),
    }


def _fallback_order_priorities(orders: list[dict[str, Any]]) -> dict[str, Any]:
    prioritized = []
    score_map = {"high": 3, "medium": 2, "low": 1}
    for order in orders:
        priority, reason, confidence = _urgency_for_order(order)
        prioritized.append(
            {
                "order_id": order.get("order_id"),
                "patient_name": order.get("patient_name"),
                "status": order.get("status"),
                "priority": priority,
                "reason": reason,
                "confidence": confidence,
                "items_preview": [item.get("name") for item in order.get("items", [])[:3] if isinstance(item, dict) and item.get("name")],
            }
        )
    prioritized.sort(key=lambda item: (-score_map.get(item["priority"], 0), -item["confidence"], int(item["order_id"] or 0)))
    return {
        "orders": prioritized,
        "confidence": _bounded_confidence(mean([item["confidence"] for item in prioritized]), default=74) if prioritized else 74,
    }


class AIPharmacyIntelligence:
    @cache_result(ttl=1800)
    async def generate_demand_forecast(self, pharmacy_id: int, snapshot: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are an AI pharmacy analyst helping a store owner forecast demand for the next 7 days.
Use the live order history and current inventory below. Avoid generic advice.

STORE SUMMARY:
{json.dumps(snapshot["aggregate"], indent=2)}

MEDICINE SALES:
{json.dumps(snapshot["medicine_sales"][:40], indent=2)}

CURRENT INVENTORY:
{json.dumps(snapshot["inventory_data"][:40], indent=2)}

Return ONLY valid JSON:
{{
  "high_demand_medicines": [
    {{"name": "", "current_stock": 0, "predicted_sales": 0, "days_until_out": 0, "confidence": 0}}
  ],
  "low_demand_medicines": [
    {{"name": "", "current_stock": 0, "days_without_sale": 0, "confidence": 0}}
  ],
  "restock_urgent": [
    {{"name": "", "suggested_quantity": 0, "supplier": "", "confidence": 0}}
  ],
  "trending_categories": ["category1", "category2"],
  "insight": "AI-generated business insight",
  "confidence": 0
}}
"""
        fallback = _fallback_forecast(snapshot)
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a precise pharmacy analytics assistant. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=1500,
            )
            payload = parse_json_response(response)
            return self._normalize_forecast(payload, fallback)
        except Exception as exc:
            logger.warning("AI pharmacy demand forecast failed for pharmacy_id=%s: %s", pharmacy_id, exc)
            return fallback

    async def optimize_pricing(
        self,
        medicine_name: str,
        current_price: float,
        competitor_prices: list[float],
        demand_score: int,
    ) -> dict[str, Any]:
        prompt = f"""
You are an AI pharmacy pricing analyst.

Medicine: {medicine_name}
Current price: Rs {current_price}
Competitor prices: {competitor_prices}
Demand score: {demand_score}

Return ONLY valid JSON:
{{
  "current_price": {round(current_price, 2)},
  "suggested_price": 0,
  "change_percent": 0,
  "reasoning": "AI explanation",
  "expected_sales_impact": "increase|decrease|stable|controlled",
  "confidence": 0
}}
"""
        fallback = self._fallback_price_optimization(medicine_name, current_price, competitor_prices, demand_score)
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a careful pharmacy pricing assistant. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=700,
            )
            payload = parse_json_response(response)
            suggested_price = float(payload.get("suggested_price", fallback["suggested_price"]) or fallback["suggested_price"])
            change_percent = round(((suggested_price - current_price) / current_price) * 100, 2) if current_price else 0
            return {
                "medicine_name": medicine_name,
                "current_price": round(current_price, 2),
                "suggested_price": round(suggested_price, 2),
                "change_percent": change_percent,
                "reasoning": str(payload.get("reasoning") or fallback["reasoning"]).strip(),
                "expected_sales_impact": str(payload.get("expected_sales_impact") or fallback["expected_sales_impact"]).strip().lower(),
                "confidence": _bounded_confidence(payload.get("confidence"), fallback["confidence"]),
            }
        except Exception as exc:
            logger.warning("AI pharmacy price optimization failed for medicine=%s: %s", medicine_name, exc)
            return fallback

    async def prioritize_orders(self, pharmacy_id: int, orders: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = f"""
You are an AI pharmacy triage assistant. Sort these orders by business and medical urgency.

ORDERS:
{json.dumps(orders[:20], indent=2)}

Rules:
- Prescription medicines should rise to the top.
- Chronic care continuity should rank high.
- Fever/pain/acute symptom baskets rank medium unless prescriptions are present.
- Wellness-only baskets rank lower.

Return ONLY valid JSON:
{{
  "orders": [
    {{
      "order_id": 0,
      "patient_name": "",
      "status": "",
      "priority": "high|medium|low",
      "reason": "",
      "confidence": 0
    }}
  ],
  "confidence": 0
}}
"""
        fallback = _fallback_order_priorities(orders)
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a precise pharmacy operations assistant. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=1200,
            )
            payload = parse_json_response(response)
            return self._normalize_priorities(payload, orders, fallback)
        except Exception as exc:
            logger.warning("AI pharmacy order prioritization failed for pharmacy_id=%s: %s", pharmacy_id, exc)
            return fallback

    @cache_result(ttl=1800)
    async def generate_daily_insights(self, pharmacy_id: int, snapshot: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are an AI business advisor for a pharmacy owner. Use only the live metrics below.

STORE SUMMARY:
{json.dumps(snapshot["aggregate"], indent=2)}

TOP CUSTOMERS:
{json.dumps(snapshot["top_customers"][:10], indent=2)}

MEDICINE SALES:
{json.dumps(snapshot["medicine_sales"][:30], indent=2)}

Return ONLY valid JSON:
{{
  "tip": "One actionable tip for today",
  "focus_area": "inventory|marketing|service|pricing",
  "alert": "Urgent alert if any",
  "opportunity": "Sales opportunity",
  "message": "Personalized message",
  "customer_insights": {{
    "trending_medicines": [
      {{"name": "", "weekly_units": 0, "category": "", "confidence": 0}}
    ],
    "top_customers": [
      {{"customer_name": "", "orders_count": 0, "total_spend": 0}}
    ],
    "customer_signal": "",
    "confidence": 0
  }},
  "pricing_opportunities": [
    {{
      "medicine_name": "",
      "current_price": 0,
      "suggested_price": 0,
      "change_percent": 0,
      "expected_sales_impact": "increase|decrease|stable|controlled",
      "confidence": 0
    }}
  ],
  "confidence": 0
}}
"""
        fallback = _fallback_daily_insights(snapshot)
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a precise pharmacy owner copilot. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=1800,
            )
            payload = parse_json_response(response)
            return self._normalize_daily(payload, fallback)
        except Exception as exc:
            logger.warning("AI pharmacy daily insights failed for pharmacy_id=%s: %s", pharmacy_id, exc)
            return fallback

    def _normalize_forecast(self, payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        return {
            "high_demand_medicines": self._normalize_medicine_entries(
                payload.get("high_demand_medicines"),
                fallback["high_demand_medicines"],
                required_keys=("name", "current_stock", "predicted_sales", "days_until_out"),
            ),
            "low_demand_medicines": self._normalize_medicine_entries(
                payload.get("low_demand_medicines"),
                fallback["low_demand_medicines"],
                required_keys=("name", "current_stock", "days_without_sale"),
            ),
            "restock_urgent": self._normalize_medicine_entries(
                payload.get("restock_urgent"),
                fallback["restock_urgent"],
                required_keys=("name", "suggested_quantity", "supplier"),
            ),
            "trending_categories": [str(item).strip() for item in (payload.get("trending_categories") or fallback["trending_categories"]) if str(item).strip()][:4],
            "insight": str(payload.get("insight") or fallback["insight"]).strip(),
            "confidence": _bounded_confidence(payload.get("confidence"), fallback["confidence"]),
        }

    def _normalize_daily(self, payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        customer_raw = payload.get("customer_insights") if isinstance(payload.get("customer_insights"), dict) else {}
        fallback_customer = fallback["customer_insights"]
        customer_insights = {
            "trending_medicines": self._normalize_medicine_entries(
                customer_raw.get("trending_medicines"),
                fallback_customer["trending_medicines"],
                required_keys=("name", "weekly_units", "category"),
            ),
            "top_customers": [
                {
                    "customer_name": str(item.get("customer_name") or "").strip(),
                    "orders_count": int(item.get("orders_count") or 0),
                    "total_spend": round(float(item.get("total_spend") or 0), 2),
                }
                for item in (customer_raw.get("top_customers") or fallback_customer["top_customers"])
                if isinstance(item, dict) and str(item.get("customer_name") or "").strip()
            ][:4],
            "customer_signal": str(customer_raw.get("customer_signal") or fallback_customer["customer_signal"]).strip(),
            "confidence": _bounded_confidence(customer_raw.get("confidence"), fallback_customer["confidence"]),
        }
        pricing_opportunities = []
        for item in (payload.get("pricing_opportunities") or fallback["pricing_opportunities"]):
            if not isinstance(item, dict) or not str(item.get("medicine_name") or "").strip():
                continue
            current_price = round(float(item.get("current_price") or 0), 2)
            suggested_price = round(float(item.get("suggested_price") or current_price), 2)
            change_percent = round(float(item.get("change_percent") or 0), 2)
            pricing_opportunities.append(
                {
                    "medicine_name": str(item.get("medicine_name")).strip(),
                    "current_price": current_price,
                    "suggested_price": suggested_price,
                    "change_percent": change_percent,
                    "expected_sales_impact": str(item.get("expected_sales_impact") or "stable").strip().lower(),
                    "confidence": _bounded_confidence(item.get("confidence"), 74),
                }
            )
        return {
            "tip": str(payload.get("tip") or fallback["tip"]).strip(),
            "focus_area": str(payload.get("focus_area") or fallback["focus_area"]).strip().lower(),
            "alert": str(payload.get("alert") or fallback["alert"]).strip(),
            "opportunity": str(payload.get("opportunity") or fallback["opportunity"]).strip(),
            "message": str(payload.get("message") or fallback["message"]).strip(),
            "customer_insights": customer_insights,
            "pricing_opportunities": pricing_opportunities[:4],
            "confidence": _bounded_confidence(payload.get("confidence"), fallback["confidence"]),
        }

    def _normalize_priorities(self, payload: dict[str, Any], source_orders: list[dict[str, Any]], fallback: dict[str, Any]) -> dict[str, Any]:
        by_id = {int(item.get("order_id") or 0): item for item in source_orders}
        priorities = []
        for item in payload.get("orders") or []:
            if not isinstance(item, dict):
                continue
            order_id = int(item.get("order_id") or 0)
            if order_id not in by_id:
                continue
            order = by_id[order_id]
            priorities.append(
                {
                    "order_id": order_id,
                    "patient_name": str(item.get("patient_name") or order.get("patient_name") or "").strip(),
                    "status": str(item.get("status") or order.get("status") or "").strip(),
                    "priority": str(item.get("priority") or "medium").strip().lower(),
                    "reason": str(item.get("reason") or "").strip() or "AI marked this order for review.",
                    "confidence": _bounded_confidence(item.get("confidence"), 76),
                    "items_preview": [sub_item.get("name") for sub_item in order.get("items", [])[:3] if isinstance(sub_item, dict) and sub_item.get("name")],
                }
            )
        if not priorities:
            return fallback
        score_map = {"high": 3, "medium": 2, "low": 1}
        priorities.sort(key=lambda item: (-score_map.get(item["priority"], 0), -item["confidence"], item["order_id"]))
        return {
            "orders": priorities[:8],
            "confidence": _bounded_confidence(payload.get("confidence"), fallback["confidence"]),
        }

    def _normalize_medicine_entries(
        self,
        items: Any,
        fallback: list[dict[str, Any]],
        *,
        required_keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        normalized = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            entry = {"name": name}
            for key in required_keys:
                if key == "name":
                    continue
                value = item.get(key)
                if key in {"current_stock", "predicted_sales", "days_without_sale", "suggested_quantity", "weekly_units"}:
                    try:
                        entry[key] = max(0, int(value or 0))
                    except (TypeError, ValueError):
                        entry[key] = 0
                elif key == "days_until_out":
                    try:
                        entry[key] = round(float(value or 0), 1)
                    except (TypeError, ValueError):
                        entry[key] = 0
                else:
                    entry[key] = str(value or "").strip()
            entry["confidence"] = _bounded_confidence(item.get("confidence"), 74)
            normalized.append(entry)
        return normalized[:5] or fallback

    def _fallback_price_optimization(
        self,
        medicine_name: str,
        current_price: float,
        competitor_prices: list[float],
        demand_score: int,
    ) -> dict[str, Any]:
        competitor_avg = mean(competitor_prices) if competitor_prices else current_price
        if demand_score >= 75:
            suggested = max(current_price, round(min(current_price * 1.04, competitor_avg * 1.02), 2))
            impact = "controlled"
            reasoning = "Demand is strong enough to hold or slightly improve margin without sharply risking conversion."
        elif demand_score <= 35:
            suggested = round(min(current_price, competitor_avg) * 0.98, 2)
            impact = "increase"
            reasoning = "Demand is soft, so a lighter price point can help move stock and improve conversion."
        else:
            suggested = round((current_price + competitor_avg) / 2, 2)
            impact = "stable"
            reasoning = "Current demand looks balanced, so pricing should stay near the market center."
        return {
            "medicine_name": medicine_name,
            "current_price": round(current_price, 2),
            "suggested_price": round(suggested, 2),
            "change_percent": round(((suggested - current_price) / current_price) * 100, 2) if current_price else 0,
            "reasoning": reasoning,
            "expected_sales_impact": impact,
            "confidence": _bounded_confidence(72 + min(max(demand_score, 0), 20)),
        }


ai_pharmacy = AIPharmacyIntelligence()
