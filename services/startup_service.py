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
from services.analytics_service import get_revenue_metrics, load_events


_LOCK = Lock()


def _startup_data_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "startup_demo.json"


def _default_demo_state() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date()
    metrics_series = []
    for day in range(30):
        current = today - timedelta(days=29 - day)
        metrics_series.append(
            {
                "date": current.isoformat(),
                "consultations": 12 + day,
                "panchakarma_bookings": 2 + (day % 4),
                "product_orders": 18 + (day * 2),
                "new_patients": 5 + (day % 6),
                "daily_active_users": 110 + (day * 9),
                "kits_sold": 3 + (day % 5),
                "interaction_checks": 9 + (day % 7),
                "community_posts": 1 + (day % 4),
                "referral_signups": 2 + (day % 5),
            }
        )

    verified_doctors = [
        {
            "name": f"Dr. Ayurveda Demo {index}",
            "registration": f"BAMS-DEMO-{1000 + index}",
            "qualification": "BAMS, MD Ayurveda" if index % 3 == 0 else "BAMS",
            "specialization": random.choice(
                [
                    "Digestive care",
                    "Pain management",
                    "Women's health",
                    "Panchakarma",
                    "Lifestyle disorders",
                ]
            ),
            "experience": 4 + (index % 18),
        }
        for index in range(1, 51)
    ]

    panchakarma_centers = [
        {
            "id": index,
            "name": f"Demo Panchakarma Center {index}",
            "city": random.choice(["Delhi NCR", "Bengaluru", "Pune", "Mumbai", "Jaipur"]),
            "rating": round(4.5 + ((index % 5) * 0.1), 1),
            "reviews": 40 + (index * 3),
            "price": 1800 + (index * 45),
            "treatment": random.choice(["Vamana", "Virechana", "Basti", "Nasya"]),
            "amenities": ["Doctor review", "Diet kitchen", "Private suite"] if index % 2 else ["Pickup support", "Weekend slots", "Women therapists"],
        }
        for index in range(1, 101)
    ]

    products = []
    prakritis = ("vata", "pitta", "kapha")
    for index in range(1, 501):
        tag = prakritis[index % 3]
        products.append(
            {
                "id": f"prod_{index}",
                "name": f"Demo Product {index}",
                "prakriti": tag,
                "category": random.choice(["digestion", "immunity", "stress", "pain_relief", "daily_routine"]),
                "price": 199 + (index % 20) * 35,
            }
        )

    patient_journeys = [
        {
            "name": f"Patient Journey {index}",
            "condition": random.choice(["Arthritis", "PCOS", "Acidity", "Diabetes Type 2", "Anxiety"]),
            "improvement": random.choice(["48% better", "61% better", "70% relief", "Regular cycle in 3 months"]),
            "system": random.choice(["Ayurveda", "Integrated", "Modern + Ayurveda"]),
        }
        for index in range(1, 21)
    ]

    testimonials = [
        {"name": "Rajesh K.", "condition": "Arthritis", "improvement": "70% relief"},
        {"name": "Priya S.", "condition": "PCOS", "improvement": "Regular cycle in 3 months"},
        {"name": "Ankit M.", "condition": "Acidity", "improvement": "Much better digestion in 6 weeks"},
        {"name": "Minal P.", "condition": "Stress and insomnia", "improvement": "Sleep improved in 21 days"},
    ]

    return {
        "metrics": {
            "daily_active_users": 1842,
            "consultations_completed": 1264,
            "panchakarma_bookings": 187,
            "personalized_kits_sold": 416,
            "interaction_checks_performed": 982,
            "community_posts": 154,
            "referral_signups": 288,
            "avg_order_value": 500,
            "patient_retention_90d": 67,
            "doctor_rating": 4.9,
        },
        "growth_metrics": {
            "dau": 1842,
            "dau_growth": 14,
            "conversion_rate": 8.6,
            "conversion_growth": 1.8,
            "customer_ltv": 6840,
            "ltv_growth": 11,
            "churn_rate": 3.2,
            "churn_reduction": 0.9,
        },
        "referral": {
            "referral_code": "KASH-HEAL-500",
            "referral_count": 12,
            "referral_earnings": 6000,
            "next_milestone": 2000,
            "claims": [],
        },
        "waitlist": {
            "feature_name": "Integrated chronic care programs",
            "waitlist_count": 482,
            "total_waitlist": 1200,
            "user_position": 138,
            "entries": [],
        },
        "verified_doctors": verified_doctors,
        "panchakarma_centers": panchakarma_centers,
        "products": products,
        "patient_journeys": patient_journeys,
        "testimonials": testimonials,
        "community_feed": [
            {
                "user_name": "Ananya",
                "condition": "PCOS support",
                "content": "Completed week 3 of my dinacharya challenge and my energy curve is finally stable.",
                "likes": 186,
                "comments": 24,
                "shares": 11,
            },
            {
                "user_name": "Rahul",
                "condition": "Cervical pain recovery",
                "content": "My vaidya shared a Panchakarma progression plan and I posted the improvement timeline for my family doctor too.",
                "likes": 149,
                "comments": 17,
                "shares": 8,
            },
        ],
        "metrics_series": metrics_series,
    }


def _load_state() -> dict[str, Any]:
    path = _startup_data_path()
    if not path.exists():
        state = _default_demo_state()
        _save_state(state)
        return state
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else _default_demo_state()
    except Exception:
        state = _default_demo_state()
        _save_state(state)
        return state


def _save_state(state: dict[str, Any]) -> None:
    path = _startup_data_path()
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def bootstrap_demo_state(force: bool = False) -> dict[str, Any]:
    with _LOCK:
        path = _startup_data_path()
        if force or not path.exists():
            state = _default_demo_state()
            _save_state(state)
            return state
        return _load_state()


def store_demo_metrics(metric_rows: list[dict[str, Any]]) -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        state["metrics_series"] = metric_rows
        if metric_rows:
            latest = metric_rows[-1]
            state.setdefault("metrics", {}).update(
                {
                    "daily_active_users": int(latest.get("daily_active_users", 0) or 0),
                    "consultations_completed": int(sum(int(item.get("consultations", 0) or 0) for item in metric_rows)),
                    "panchakarma_bookings": int(sum(int(item.get("panchakarma_bookings", 0) or 0) for item in metric_rows)),
                    "personalized_kits_sold": int(sum(int(item.get("kits_sold", 0) or 0) for item in metric_rows)),
                    "interaction_checks_performed": int(sum(int(item.get("interaction_checks", 0) or 0) for item in metric_rows)),
                    "community_posts": int(sum(int(item.get("community_posts", 0) or 0) for item in metric_rows)),
                    "referral_signups": int(sum(int(item.get("referral_signups", 0) or 0) for item in metric_rows)),
                }
            )
        _save_state(state)
        return state


def get_competitor_matrix() -> list[dict[str, str]]:
    return [
        {
            "feature": "Integrated Ayurveda + modern medicine workflow",
            "competitors": "Usually split across separate apps or generic teleconsultation flows",
            "us": "Single care journey with EMR, prescriptions, labs, outcomes, and commerce",
        },
        {
            "feature": "Classical Ayurveda reasoning support",
            "competitors": "Basic wellness content or broad symptom checkers",
            "us": "Samhita-grounded retrieval, prakriti, vikriti, agni, ama, and srotas support",
        },
        {
            "feature": "Herb-drug interaction visibility",
            "competitors": "Mostly focused on drug-only safety checks",
            "us": "Cross-system Ayurveda + allopathy interaction prompts",
        },
        {
            "feature": "Panchakarma operations",
            "competitors": "Rarely productized end to end",
            "us": "Scheduling, treatment planning, outcomes, and marketplace-ready discovery",
        },
        {
            "feature": "Continuity after consultation",
            "competitors": "Appointment or delivery focused",
            "us": "Follow-ups, WhatsApp sharing, refill signals, subscriptions, and outcomes tracking",
        },
    ]


def get_panchakarma_centers(limit: int | None = None) -> list[dict[str, Any]]:
    items = deepcopy(_load_state().get("panchakarma_centers", []))
    return items[:limit] if limit else items


def get_verified_practitioners(limit: int | None = None) -> list[dict[str, Any]]:
    items = deepcopy(_load_state().get("verified_doctors", []))
    return items[:limit] if limit else items


def get_verified_testimonials() -> list[dict[str, str]]:
    seeded = deepcopy(_load_state().get("testimonials", []))
    return [
        {
            "name": item.get("name", "Verified patient"),
            "condition": item.get("condition", "Integrated care"),
            "content": f"{item.get('improvement', 'Meaningful improvement')} with guided Ayurveda-led care.",
            "proof_url": "/investor-demo",
        }
        for item in seeded[:4]
    ]


def get_wellness_feed() -> list[dict[str, Any]]:
    return deepcopy(_load_state().get("community_feed", []))


def get_patient_journeys() -> list[dict[str, Any]]:
    return deepcopy(_load_state().get("patient_journeys", []))


def get_personalized_kits() -> dict[str, list[dict[str, Any]]]:
    products = _load_state().get("products", [])
    grouped: dict[str, list[dict[str, Any]]] = {"vata": [], "pitta": [], "kapha": []}
    descriptions = {
        "vata": "For dryness, irregular appetite, light sleep, and stressy energy swings.",
        "pitta": "For acidity, heat, irritability, and inflammatory digestive discomfort.",
        "kapha": "For heaviness, congestion, sluggish digestion, and low morning energy.",
    }
    for prakriti in grouped:
        matching = [item["name"] for item in products if str(item.get("prakriti")) == prakriti][:3]
        grouped[prakriti].append(
            {
                "id": f"kit_{prakriti}_core",
                "name": f"{prakriti.title()} Balance Kit",
                "description": descriptions[prakriti],
                "products": matching or [f"{prakriti.title()} support tonic", f"{prakriti.title()} routine support"],
                "price": 849 if prakriti == "kapha" else 899 if prakriti == "vata" else 999,
            }
        )
    return grouped


def get_growth_metrics() -> dict[str, Any]:
    state = _load_state()
    metrics = deepcopy(state.get("growth_metrics", {}))
    stored = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    analytics_revenue = get_revenue_metrics()
    metrics["traction_metrics"] = {
        "daily_active_users": int(stored.get("daily_active_users", metrics.get("dau", 0)) or 0),
        "consultations_completed": int(stored.get("consultations_completed", 0) or 0),
        "panchakarma_bookings": int(stored.get("panchakarma_bookings", 0) or 0),
        "personalized_kits_sold": int(stored.get("personalized_kits_sold", 0) or 0),
        "interaction_checks_performed": int(stored.get("interaction_checks_performed", 0) or 0),
        "community_posts": int(stored.get("community_posts", 0) or 0),
        "referral_signups": int(stored.get("referral_signups", 0) or 0),
    }
    metrics["revenue_streams"] = [
        "Consultation fees",
        "Panchakarma booking commission",
        "Personalized kit subscriptions",
        "Pharmacy fulfillment fees",
        "Enterprise EMR licensing",
        "Data insight reports",
    ]
    metrics["estimated_revenue"] = int(analytics_revenue.get("estimated_revenue", 0) or 0)
    metrics["metrics_series"] = deepcopy(state.get("metrics_series", []))
    return metrics


def get_referral_snapshot() -> dict[str, Any]:
    return deepcopy(_load_state().get("referral", {}))


def claim_referral_bonus(referral_code: str, email: str = "") -> dict[str, Any]:
    clean_code = str(referral_code or "").strip().upper()
    clean_email = str(email or "").strip().lower()
    with _LOCK:
        state = _load_state()
        referral = state.setdefault("referral", {})
        if clean_code != str(referral.get("referral_code", "")).upper():
            return {"success": False, "error": "invalid_referral_code"}
        claims = referral.setdefault("claims", [])
        if clean_email and any(str(item.get("email", "")).lower() == clean_email for item in claims if isinstance(item, dict)):
            return {"success": False, "error": "already_claimed"}
        claims.append(
            {
                "email": clean_email,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        referral["referral_count"] = int(referral.get("referral_count", 0) or 0) + 1
        referral["referral_earnings"] = int(referral.get("referral_earnings", 0) or 0) + 500
        state.setdefault("metrics", {})["referral_signups"] = int(state.setdefault("metrics", {}).get("referral_signups", 0) or 0) + 1
        _save_state(state)
    track_event("referral_claimed", referral_code=clean_code, email=clean_email)
    return {"success": True, "referral": deepcopy(referral), "bonus_for_referrer": 500, "bonus_for_new_user": 250}


def get_waitlist_snapshot() -> dict[str, Any]:
    snapshot = deepcopy(_load_state().get("waitlist", {}))
    total = int(snapshot.get("total_waitlist", snapshot.get("waitlist_count", 0)) or 0)
    snapshot.setdefault("user_position", max(1, total - 1062))
    return snapshot


def join_waitlist(email: str) -> dict[str, Any]:
    clean_email = str(email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        return {"success": False, "error": "valid_email_required"}
    with _LOCK:
        state = _load_state()
        waitlist = state.setdefault("waitlist", {})
        entries = waitlist.setdefault("entries", [])
        if any(str(item.get("email", "")).lower() == clean_email for item in entries if isinstance(item, dict)):
            return {"success": False, "error": "already_joined", "waitlist": deepcopy(waitlist)}
        entries.append({"email": clean_email, "joined_at": datetime.now(timezone.utc).isoformat()})
        waitlist["waitlist_count"] = int(waitlist.get("waitlist_count", 0) or 0) + 1
        waitlist["total_waitlist"] = int(waitlist.get("total_waitlist", waitlist["waitlist_count"]) or 0) + 1
        waitlist["user_position"] = max(1, int(waitlist.get("total_waitlist", 1) or 1) - len(entries))
        _save_state(state)
    track_event("waitlist_joined", email=clean_email, feature=get_waitlist_snapshot().get("feature_name", "unknown"))
    return {"success": True, "waitlist": get_waitlist_snapshot()}


def get_investor_demo_payload() -> dict[str, Any]:
    state = _load_state()
    metrics = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    return {
        "steps": [
            {
                "title": "Patient registers and prakriti is detected",
                "description": "Constitution-led onboarding creates a deeper care profile than a generic health app.",
                "highlight": "Competitors do not lead with prakriti-based care intelligence.",
            },
            {
                "title": "Dual AI diagnosis compares Ayurveda and modern medicine",
                "description": "Doctors review both systems side by side before finalizing next steps.",
                "highlight": "Integrated care is the flagship moat.",
            },
            {
                "title": "Personalized treatment and commerce flow",
                "description": "Diet, herbs, prescriptions, kits, and follow-up all remain in one product surface.",
                "highlight": "This turns care continuity into recurring revenue.",
            },
            {
                "title": "Outcome prediction and patient retention",
                "description": "Expected progress and long-term reminders help clinics prove healing, not just transactions.",
                "highlight": "Measured outcomes build trust with both patients and investors.",
            },
        ],
        "metrics": {
            "avg_order_value": int(metrics.get("avg_order_value", 500) or 500),
            "patient_retention_90d": int(metrics.get("patient_retention_90d", 67) or 67),
            "doctor_rating": float(metrics.get("doctor_rating", 4.9) or 4.9),
        },
    }


def get_social_proof_activity() -> str:
    state = _load_state()
    testimonials = state.get("testimonials", []) if isinstance(state.get("testimonials"), list) else []
    metrics = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    snippets = [
        f"{random.choice(['Priya', 'Amit', 'Neha', 'Rahul'])} just joined the waitlist for integrated chronic care",
        f"{int(metrics.get('interaction_checks_performed', 0) or 0)} herb interaction checks performed this month",
        f"{int(metrics.get('panchakarma_bookings', 0) or 0)} Panchakarma bookings completed in demo mode",
    ]
    if testimonials:
        sample = random.choice(testimonials)
        snippets.append(f"New success story: {sample.get('name', 'Verified patient')} saw {sample.get('improvement', 'visible improvement')}")
    return random.choice(snippets)


def get_demo_inventory_snapshot() -> dict[str, int]:
    state = _load_state()
    return {
        "verified_doctors": len(state.get("verified_doctors", [])),
        "panchakarma_centers": len(state.get("panchakarma_centers", [])),
        "products": len(state.get("products", [])),
        "patient_journeys": len(state.get("patient_journeys", [])),
    }


def get_event_based_startup_counts() -> dict[str, int]:
    counts = {
        "consultations_completed": 0,
        "interaction_checks_performed": 0,
        "community_posts": 0,
    }
    for item in load_events():
        event_name = str(item.get("event_name") or "")
        if event_name == "ai_analyzer_used":
            counts["interaction_checks_performed"] += 1
        elif event_name == "subscription_created":
            counts["consultations_completed"] += 1
    return counts
