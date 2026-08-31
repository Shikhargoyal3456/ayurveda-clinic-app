from __future__ import annotations

import json
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.analytics import track_event
from app.config import settings
from services.offer_engine import AIOfferEngine
from services.startup_service import get_personalized_kits


_LOCK = Lock()
_DEFAULT_USER = "guest"


def _path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "superapp_data.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_products() -> list[dict[str, Any]]:
    base = [
        ("Ashwagandha Tablets", "ayurveda", "stress", 349, 499, "Vata", True),
        ("Guduchi Capsules", "ayurveda", "immunity", 299, 399, "Pitta", True),
        ("Sitopaladi Churna", "ayurveda", "cold_cough", 189, 249, "Kapha", True),
        ("Paracetamol 650", "allopathy", "pain_relief", 35, 45, "All", False),
        ("Vitamin D3", "wellness", "supplements", 499, 699, "All", False),
        ("Omega 3 Capsules", "wellness", "supplements", 599, 799, "All", False),
        ("Neem Face Wash", "wellness", "skin", 249, 349, "Pitta", False),
        ("Amla Juice", "ayurveda", "immunity", 399, 525, "Pitta", False),
        ("ORS Sachet", "allopathy", "digestion", 25, 35, "All", False),
        ("Brahmi Vati", "ayurveda", "mind_calm", 289, 355, "Vata", True),
        ("Protein Nutrition Mix", "wellness", "fitness", 899, 1199, "All", False),
        ("Turmeric Extract", "ayurveda", "inflammation", 449, 599, "Kapha", False),
    ]
    products: list[dict[str, Any]] = []
    for idx, item in enumerate(base, start=1):
        name, system, category, price, mrp, prakriti, rx = item
        products.append(
            {
                "id": idx,
                "name": name,
                "system": system,
                "category": category,
                "price": price,
                "mrp": mrp,
                "rating": round(4.2 + (idx % 6) * 0.1, 1),
                "reviews": 90 + idx * 14,
                "prakriti": prakriti.lower(),
                "prescription_required": rx,
                "offer": max(5, round((1 - price / mrp) * 100)),
                "stock": 15 + idx * 3,
                "image": "",
            }
        )
    return products


def _seed_lab_tests() -> list[dict[str, Any]]:
    return [
        {"id": 1, "name": "Complete Blood Count", "category": "hematology", "price": 399, "report_time": "12 hrs", "preparation": "No fasting required"},
        {"id": 2, "name": "Thyroid Profile", "category": "endocrine", "price": 699, "report_time": "24 hrs", "preparation": "No fasting required"},
        {"id": 3, "name": "HbA1c", "category": "diabetes", "price": 549, "report_time": "10 hrs", "preparation": "No fasting required"},
        {"id": 4, "name": "Lipid Profile", "category": "cardiac", "price": 799, "report_time": "12 hrs", "preparation": "10 hour fasting"},
        {"id": 5, "name": "Vitamin D", "category": "wellness", "price": 899, "report_time": "24 hrs", "preparation": "No fasting required"},
    ]


def _seed_packages() -> list[dict[str, Any]]:
    return [
        {
            "id": "pkg_full_body",
            "name": "Full Body Starter",
            "description": "Baseline metabolic, blood, and vitamin panel.",
            "tests": ["CBC", "Lipid", "HbA1c", "Vitamin D"],
            "original_price": 2699,
            "discounted_price": 1699,
            "ai_recommended": True,
        },
        {
            "id": "pkg_thyroid_women",
            "name": "Women's Thyroid & Energy",
            "description": "For fatigue, weight changes, and hormonal screening.",
            "tests": ["Thyroid", "CBC", "Vitamin D"],
            "original_price": 2299,
            "discounted_price": 1499,
            "ai_recommended": False,
        },
    ]


def _seed_articles() -> list[dict[str, Any]]:
    return [
        {"id": 1, "title": "Understanding acidity through Ayurveda and modern medicine", "category": "digestion", "summary": "A dual-system view of burning digestion patterns.", "read_time": 5, "views": 1240},
        {"id": 2, "title": "How to improve sleep hygiene with dinacharya", "category": "wellness", "summary": "Simple daily habits that stabilize Vata and improve sleep.", "read_time": 4, "views": 980},
        {"id": 3, "title": "When joint pain needs Panchakarma evaluation", "category": "pain", "summary": "Signals that conservative care may need a deeper detox pathway.", "read_time": 6, "views": 760},
        {"id": 4, "title": "Reading your lipid profile without panic", "category": "labs", "summary": "How to interpret common cholesterol markers.", "read_time": 5, "views": 1530},
    ]


def _default_state() -> dict[str, Any]:
    return {
        "products": _seed_products(),
        "lab_tests": _seed_lab_tests(),
        "lab_packages": _seed_packages(),
        "articles": _seed_articles(),
        "orders": [],
        "lab_bookings": [],
        "users": {
            _DEFAULT_USER: {
                "points": 860,
                "tier": "bronze",
                "total_spent": 4200,
                "orders": 3,
                "abandoned_carts": 1,
                "frequent_category": "ayurveda",
                "subscription_eligible": True,
                "prakriti": "vata",
            }
        },
        "subscriptions": [
            {"id": "sub_1", "user_id": _DEFAULT_USER, "medicine_name": "Ashwagandha Tablets", "frequency": "monthly", "next_delivery": (datetime.now().date() + timedelta(days=12)).isoformat(), "days_left": 12},
            {"id": "sub_2", "user_id": _DEFAULT_USER, "medicine_name": "Vitamin D3", "frequency": "quarterly", "next_delivery": (datetime.now().date() + timedelta(days=28)).isoformat(), "days_left": 28},
        ],
        "cart": {_DEFAULT_USER: []},
        "rewards": [
            {"id": "reward_1", "name": "50 Rs wallet credit", "points_required": 500, "description": "Instant reward wallet credit", "type": "wallet"},
            {"id": "reward_2", "name": "Free delivery pass", "points_required": 900, "description": "Free delivery on one order", "type": "shipping"},
            {"id": "reward_3", "name": "Lab discount voucher", "points_required": 1200, "description": "15% off on lab package", "type": "voucher"},
        ],
        "campaign_logs": [],
        "lab_partners": [
            {"name": "Thyrocare Partner", "rating": 4.8, "accreditation": "NABL"},
            {"name": "Dr Lal PathLabs Partner", "rating": 4.7, "accreditation": "NABL/CAP"},
            {"name": "Metropolis Partner", "rating": 4.6, "accreditation": "ISO"},
        ],
        "quick_support": [],
    }


def _load() -> dict[str, Any]:
    if not _path().exists():
        state = _default_state()
        _save(state)
        return state
    try:
        payload = json.loads(_path().read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else _default_state()
    except Exception:
        state = _default_state()
        _save(state)
        return state


def _save(state: dict[str, Any]) -> None:
    _path().write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def bootstrap_superapp(force: bool = False) -> dict[str, Any]:
    with _LOCK:
        if force or not _path().exists():
            state = _default_state()
            _save(state)
            return state
        return _load()


def get_products(query: str = "", category: str = "", require_rx: bool | None = None) -> list[dict[str, Any]]:
    items = deepcopy(_load().get("products", []))
    query_text = str(query or "").strip().lower()
    category_text = str(category or "").strip().lower()
    results: list[dict[str, Any]] = []
    for item in items:
        if query_text and query_text not in f"{item.get('name','')} {item.get('category','')} {item.get('system','')}".lower():
            continue
        if category_text and category_text not in {str(item.get("system", "")).lower(), str(item.get("category", "")).lower()}:
            continue
        if require_rx is not None and bool(item.get("prescription_required")) != require_rx:
            continue
        results.append(item)
    return results


def get_product_categories() -> list[dict[str, Any]]:
    return [
        {"key": "allopathy", "label": "Allopathy", "icon": "fa-capsules"},
        {"key": "ayurveda", "label": "Ayurveda", "icon": "fa-leaf"},
        {"key": "wellness", "label": "Wellness", "icon": "fa-spa"},
        {"key": "supplements", "label": "Supplements", "icon": "fa-dumbbell"},
    ]


def ai_extract_prescription(_: str = "") -> list[dict[str, Any]]:
    items = get_products()[:3]
    return [{"name": item["name"], "quantity": 1, "dosage": "As directed"} for item in items]


def get_user_profile(user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    state = _load()
    user = deepcopy(state.get("users", {}).get(user_id, state.get("users", {}).get(_DEFAULT_USER, {})))
    user["user_id"] = user_id
    return user


def get_cart(user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    state = _load()
    items = deepcopy(state.get("cart", {}).get(user_id, []))
    total = round(sum(float(item.get("price", 0) or 0) * int(item.get("quantity", 1) or 1) for item in items), 2)
    offers = AIOfferEngine().generate_personalized_offers(get_user_profile(user_id))
    discounted_total, best_offer = AIOfferEngine().apply_best_offer(total, offers)
    return {
        "items": items,
        "total": total,
        "discounted_total": discounted_total,
        "best_offer": best_offer,
        "suggestions": get_smart_suggestions(items),
    }


def add_to_cart(product_id: int, quantity: int = 1, user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    quantity = max(1, int(quantity or 1))
    with _LOCK:
        state = _load()
        product = next((item for item in state.get("products", []) if int(item.get("id", 0)) == int(product_id)), None)
        if product is None:
            return {"success": False, "error": "product_not_found"}
        user_cart = state.setdefault("cart", {}).setdefault(user_id, [])
        existing = next((item for item in user_cart if int(item.get("product_id", 0)) == int(product_id)), None)
        if existing:
            existing["quantity"] = int(existing.get("quantity", 1) or 1) + quantity
        else:
            user_cart.append(
                {
                    "product_id": product["id"],
                    "name": product["name"],
                    "price": product["price"],
                    "mrp": product["mrp"],
                    "quantity": quantity,
                    "category": product["category"],
                }
            )
        _save(state)
    track_event("superapp_cart_add", user_id=user_id, product_id=product_id, quantity=quantity)
    return {"success": True, "cart": get_cart(user_id)}


def get_smart_suggestions(cart_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products = _load().get("products", [])
    cart_categories = {str(item.get("category", "")) for item in cart_items}
    picks = [item for item in products if str(item.get("category", "")) not in cart_categories][:4]
    return deepcopy(picks)


def get_offers(user_id: str = _DEFAULT_USER) -> list[dict[str, Any]]:
    return AIOfferEngine().generate_personalized_offers(get_user_profile(user_id))


def get_best_offer(user_id: str = _DEFAULT_USER) -> dict[str, Any] | None:
    cart = get_cart(user_id)
    return cart.get("best_offer")


def calculate_dynamic_price(product_id: int, user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    product = next((item for item in _load().get("products", []) if int(item.get("id", 0)) == int(product_id)), None)
    if product is None:
        return {"success": False, "error": "product_not_found"}
    profile = get_user_profile(user_id)
    tier = str(profile.get("tier", "bronze")).lower()
    tier_discount = {"bronze": 0, "silver": 5, "gold": 10}.get(tier, 0)
    quantity = sum(int(item.get("quantity", 0) or 0) for item in get_cart(user_id).get("items", []) if int(item.get("product_id", 0)) == int(product_id))
    volume_discount = min(quantity * 2, 20)
    first_purchase_discount = 20 if int(profile.get("orders", 0) or 0) == 0 else 0
    max_discount = max(tier_discount, volume_discount, first_purchase_discount)
    final_price = round(float(product["price"]) * (1 - max_discount / 100), 2)
    return {"success": True, "product_id": product_id, "base_price": product["price"], "final_price": final_price, "discount": max_discount}


def checkout(user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    cart = get_cart(user_id)
    items = cart.get("items", [])
    if not items:
        return {"success": False, "error": "cart_empty"}
    with _LOCK:
        state = _load()
        next_id = len(state.get("orders", [])) + 1
        order = {
            "id": next_id,
            "user_id": user_id,
            "items": deepcopy(items),
            "total_amount": cart.get("discounted_total", cart.get("total", 0)),
            "status": "packed",
            "tracking_id": f"TRK{10000 + next_id}",
            "delivery_partner": random.choice(["Blink Health", "MediExpress", "QuickCare Fleet"]),
            "estimated_delivery": (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat(),
            "placed_time": _now(),
            "timeline": [
                {"status": "Order Placed", "timestamp": _now(), "completed": True},
                {"status": "Packed & Ready", "timestamp": _now(), "completed": True},
                {"status": "Out for Delivery", "timestamp": "", "completed": False},
                {"status": "Delivered", "timestamp": "", "completed": False},
            ],
        }
        state.setdefault("orders", []).append(order)
        state.setdefault("cart", {})[user_id] = []
        user = state.setdefault("users", {}).setdefault(user_id, get_user_profile(user_id))
        user["orders"] = int(user.get("orders", 0) or 0) + 1
        user["total_spent"] = float(user.get("total_spent", 0) or 0) + float(order["total_amount"])
        _save(state)
    track_event("superapp_checkout", user_id=user_id, order_id=next_id, total=order["total_amount"])
    return {"success": True, "order": order}


def get_orders(user_id: str = _DEFAULT_USER) -> list[dict[str, Any]]:
    return [deepcopy(item) for item in _load().get("orders", []) if str(item.get("user_id", "")) == user_id]


def get_order_tracking(order_id: int) -> dict[str, Any]:
    order = next((item for item in _load().get("orders", []) if int(item.get("id", 0)) == int(order_id)), None)
    if order is None:
        return {"success": False, "error": "order_not_found"}
    return {"success": True, "order": deepcopy(order), "location": {"lat": 28.6139, "lng": 77.2090, "eta": "25 min"}}


def cancel_order(order_id: int) -> dict[str, Any]:
    with _LOCK:
        state = _load()
        order = next((item for item in state.get("orders", []) if int(item.get("id", 0)) == int(order_id)), None)
        if order is None:
            return {"success": False, "error": "order_not_found"}
        order["status"] = "cancelled"
        _save(state)
    return {"success": True, "order": deepcopy(order)}


def reschedule_order(order_id: int, when: str) -> dict[str, Any]:
    with _LOCK:
        state = _load()
        order = next((item for item in state.get("orders", []) if int(item.get("id", 0)) == int(order_id)), None)
        if order is None:
            return {"success": False, "error": "order_not_found"}
        order["estimated_delivery"] = when
        _save(state)
    return {"success": True, "order": deepcopy(order)}


def get_lab_tests(query: str = "") -> list[dict[str, Any]]:
    items = deepcopy(_load().get("lab_tests", []))
    q = str(query or "").strip().lower()
    if not q:
        return items
    return [item for item in items if q in f"{item.get('name','')} {item.get('category','')}".lower()]


def get_lab_packages() -> list[dict[str, Any]]:
    return deepcopy(_load().get("lab_packages", []))


def book_lab_tests(test_ids: list[int], address: str, collection_time: str, user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    with _LOCK:
        state = _load()
        booking_id = len(state.get("lab_bookings", [])) + 1
        booking = {
            "id": booking_id,
            "user_id": user_id,
            "test_ids": test_ids,
            "collection_address": address,
            "collection_time": collection_time,
            "status": "scheduled",
            "created_at": _now(),
        }
        state.setdefault("lab_bookings", []).append(booking)
        _save(state)
    track_event("superapp_lab_booked", user_id=user_id, booking_id=booking_id, tests=len(test_ids))
    return {"success": True, "booking": booking}


def interpret_lab_report(report_text: str) -> dict[str, Any]:
    text = str(report_text or "").lower()
    flags: list[str] = []
    if "cholesterol" in text or "ldl" in text:
        flags.append("Lipid markers may need doctor review and lifestyle support.")
    if "thyroid" in text or "tsh" in text:
        flags.append("Thyroid pattern detected. Compare with symptoms and energy markers.")
    if "glucose" in text or "hba1c" in text:
        flags.append("Blood sugar markers suggest regular monitoring.")
    return {
        "summary": "AI report interpretation is advisory and should be reviewed by a clinician.",
        "flags": flags or ["No critical keywords detected from the uploaded text sample."],
        "recommendation": "Book a doctor consult if values are outside the reference range or symptoms are ongoing.",
    }


def get_loyalty(user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    user = get_user_profile(user_id)
    return {
        "user_id": user_id,
        "points": int(user.get("points", 0) or 0),
        "tier": str(user.get("tier", "bronze")),
        "total_spent": float(user.get("total_spent", 0) or 0),
    }


def get_rewards() -> list[dict[str, Any]]:
    return deepcopy(_load().get("rewards", []))


def redeem_reward(reward_id: str, user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    with _LOCK:
        state = _load()
        reward = next((item for item in state.get("rewards", []) if str(item.get("id", "")) == str(reward_id)), None)
        if reward is None:
            return {"success": False, "error": "reward_not_found"}
        user = state.setdefault("users", {}).setdefault(user_id, get_user_profile(user_id))
        points = int(user.get("points", 0) or 0)
        required = int(reward.get("points_required", 0) or 0)
        if points < required:
            return {"success": False, "error": "insufficient_points"}
        user["points"] = points - required
        _save(state)
    track_event("superapp_reward_redeemed", user_id=user_id, reward_id=reward_id)
    return {"success": True, "remaining_points": get_loyalty(user_id)["points"], "reward": deepcopy(reward)}


def get_health_articles(query: str = "") -> list[dict[str, Any]]:
    items = deepcopy(_load().get("articles", []))
    q = str(query or "").strip().lower()
    if not q:
        return items
    return [item for item in items if q in f"{item.get('title','')} {item.get('summary','')} {item.get('category','')}".lower()]


def get_trending_topics() -> list[str]:
    return ["acidity", "thyroid", "joint pain", "sleep", "vitamin deficiency", "panchakarma"]


def get_store_categories() -> list[dict[str, Any]]:
    return [
        {"name": "Ayurveda", "icon": "fa-leaf", "subcategories": ["Immunity", "Digestion", "Stress"]},
        {"name": "Wellness", "icon": "fa-spa", "subcategories": ["Supplements", "Skin", "Fitness"]},
        {"name": "Allopathy", "icon": "fa-capsules", "subcategories": ["Pain relief", "Digestion", "Cold & cough"]},
        {"name": "Diagnostics", "icon": "fa-flask", "subcategories": ["Home collection", "Packages"]},
    ]


def get_ai_recommendations(user_id: str = _DEFAULT_USER) -> list[dict[str, Any]]:
    profile = get_user_profile(user_id)
    prakriti = str(profile.get("prakriti", "vata")).lower()
    kits = get_personalized_kits().get(prakriti, [])
    suggested_names = {name for kit in kits for name in kit.get("products", [])}
    recommendations = [item for item in get_products() if item["name"] in suggested_names]
    return recommendations or get_products()[:4]


def get_support_response(message: str) -> dict[str, Any]:
    text = str(message or "").lower()
    if "track" in text and "order" in text:
        return {"reply": "You can track live order status from the tracking page. Use the latest order card to open it.", "action": "track_order"}
    if "lab" in text:
        return {"reply": "I can help you book a home sample collection slot and suggest the right package.", "action": "book_lab"}
    if "refill" in text or "prescription" in text:
        return {"reply": "Your refill workflow can be automated 7 days before medicine exhaustion.", "action": "refill_prescription"}
    if "doctor" in text or "consult" in text:
        return {"reply": "You can compare Ayurveda and modern medicine guidance, then move into consultation booking.", "action": "consult_doctor"}
    return {"reply": "I can help with medicines, lab tests, orders, subscriptions, offers, and doctor booking.", "action": "general"}


def _dynamic_health_score(profile: dict[str, Any], orders: list[dict[str, Any]], subscriptions: list[dict[str, Any]]) -> int:
    points = int(profile.get("points", 0) or 0)
    total_spent = float(profile.get("total_spent", 0) or 0)
    orders_count = len(orders)
    subscriptions_count = len(subscriptions)
    recent_orders = len([item for item in orders if item.get("placed_time")])
    score = 42
    score += min(18, subscriptions_count * 8)
    score += min(16, orders_count * 4)
    score += min(10, recent_orders * 2)
    score += min(8, points // 250)
    score += min(6, int(total_spent // 2000))
    return max(35, min(96, int(score)))


def _dynamic_health_message(score: int, subscriptions: list[dict[str, Any]], orders: list[dict[str, Any]]) -> str:
    if subscriptions and orders:
        return (
            f"Your care activity looks organized with {len(subscriptions)} tracked medicine plan(s) "
            f"and {len(orders)} recent order(s) in your journey."
        )
    if subscriptions:
        return f"You are actively tracking {len(subscriptions)} medicine plan(s), which helps keep refills predictable."
    if orders:
        return f"You have {len(orders)} recent order(s) on record, giving Kash AI enough context to guide your next step."
    return "Your dashboard will become more personalized as you place orders, track medicines, and use care services."


def _dynamic_health_insights(score: int, subscriptions: list[dict[str, Any]], orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    if subscriptions:
        soonest = min(int(item.get("days_left", 0) or 0) for item in subscriptions)
        insights.append(
            {
                "icon": "fa-solid fa-capsules",
                "title": "Refill timing",
                "description": (
                    f"Your next tracked refill window is {'today' if soonest <= 0 else f'in {soonest} day(s)'}."
                ),
            }
        )
    if orders:
        insights.append(
            {
                "icon": "fa-solid fa-truck",
                "title": "Order activity",
                "description": f"You have {len(orders)} recent order(s) shaping your current care timeline.",
            }
        )
    insights.append(
        {
            "icon": "fa-solid fa-heart-pulse",
            "title": "Care momentum",
            "description": (
                "Your current activity suggests a strong routine." if score >= 75
                else "More regular use of refill and follow-up tools will sharpen your care view."
            ),
        }
    )
    return insights[:3]


def get_dashboard_payload(user_id: str = _DEFAULT_USER) -> dict[str, Any]:
    orders = get_orders(user_id)
    subscriptions = deepcopy(_load().get("subscriptions", []))
    profile = get_user_profile(user_id)
    user_subscriptions = [item for item in subscriptions if str(item.get("user_id", "")) == user_id]
    health_score = _dynamic_health_score(profile, orders, user_subscriptions)
    return {
        "health_score": health_score,
        "health_score_percent": round(health_score * 3.39, 2),
        "health_message": _dynamic_health_message(health_score, user_subscriptions, orders),
        "subscriptions": user_subscriptions,
        "recent_orders": orders[-3:][::-1],
        "health_insights": _dynamic_health_insights(health_score, user_subscriptions, orders),
        "prakriti": profile.get("prakriti", "vata"),
    }


def auto_refill_prescription(user_id: str, prescription_name: str, medicines: list[dict[str, Any]], days_left: int) -> dict[str, Any]:
    if int(days_left or 0) > 7:
        return {"success": False, "error": "not_due"}
    with _LOCK:
        state = _load()
        order_id = len(state.get("orders", [])) + 1
        normalized_items = [
            {
                "product_id": int(item.get("product_id", 0) or 0),
                "name": str(item.get("name", "")),
                "price": float(item.get("price", 0) or 0),
                "mrp": float(item.get("mrp", item.get("price", 0)) or 0),
                "quantity": int(item.get("quantity", 1) or 1),
                "category": str(item.get("category", "prescription")),
            }
            for item in medicines
        ]
        total = round(sum(item["price"] * item["quantity"] for item in normalized_items), 2)
        order = {
            "id": order_id,
            "user_id": user_id,
            "items": normalized_items,
            "total_amount": total,
            "status": "auto_refilled",
            "tracking_id": f"ARX{10000 + order_id}",
            "delivery_partner": "AutoCare Fleet",
            "estimated_delivery": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
            "placed_time": _now(),
            "timeline": [{"status": "Auto refill created", "timestamp": _now(), "completed": True}],
            "prescription_name": prescription_name,
        }
        state.setdefault("orders", []).append(order)
        _save(state)
    track_event("superapp_auto_refill_created", user_id=user_id, order_id=order_id, prescription_name=prescription_name)
    return {"success": True, "order": order, "message": f"Prescription for {prescription_name} auto-refilled."}
