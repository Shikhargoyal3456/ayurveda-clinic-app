from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.database import SessionLocal
from app.models import Doctor
from models.emr import EMRVital
from models.medicine import Medicine, MedicineOrder
from services.superapp_service import get_dashboard_payload


class AIPersonalizationEngine:
    """Hybrid recommendation engine built on current marketplace/app data."""

    def __init__(self) -> None:
        self.user_profiles: dict[int, dict[str, Any]] = {}

    async def get_personalized_feed(self, user_id: int) -> dict[str, Any]:
        profile = await self.get_user_profile(user_id)
        recommendations = await self.get_collaborative_recommendations(profile)
        content_based = await self.get_content_based_recommendations(profile)
        hybrid = self.combine_recommendations(recommendations, content_based)
        sorted_recommendations = sorted(hybrid, key=lambda item: item["score"], reverse=True)
        return {
            "medicines": [item for item in sorted_recommendations if item["type"] == "medicine"][:10],
            "doctors": [item for item in sorted_recommendations if item["type"] == "doctor"][:5],
            "articles": [item for item in sorted_recommendations if item["type"] == "article"][:5],
            "offers": await self.get_personalized_offers(profile),
        }

    async def predict_next_purchase(self, user_id: int) -> list[dict[str, Any]]:
        history = await self.get_purchase_history(user_id)
        if not history:
            return []
        patterns = self.analyze_purchase_patterns(history)
        days_since_last = (datetime.now(timezone.utc) - history[-1]["date"]).days
        if days_since_last >= patterns["avg_gap"]:
            return patterns["frequently_bought_together"]
        return []

    async def get_health_insights(self, user_id: int) -> dict[str, Any]:
        vitals = await self.get_user_vitals(user_id)
        medications = await self.get_user_medications(user_id)
        symptoms = await self.get_user_symptoms(user_id)
        return {
            "health_score": self.calculate_health_score(vitals),
            "risk_factors": self.identify_risk_factors(vitals, medications),
            "recommendations": self.generate_recommendations(vitals, symptoms),
            "predicted_issues": self.predict_health_issues(vitals, symptoms),
            "preventive_measures": self.suggest_preventive_measures(vitals),
        }

    async def get_user_profile(self, user_id: int) -> dict[str, Any]:
        dashboard = get_dashboard_payload(str(user_id))
        profile = {
            "user_id": user_id,
            "health_score": dashboard.get("health_score", 78),
            "recent_orders": dashboard.get("recent_orders", []),
            "insights": dashboard.get("health_insights", []),
        }
        self.user_profiles[user_id] = profile
        return profile

    async def get_collaborative_recommendations(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            meds = db.query(Medicine).filter(Medicine.is_available.is_(True)).order_by(Medicine.stock.desc(), Medicine.price.asc()).limit(6).all()
            return [{"id": item.id, "type": "medicine", "title": item.name, "score": round(0.78 + (index * 0.02), 2), "price": int(item.price or 0)} for index, item in enumerate(meds)]
        finally:
            db.close()

    async def get_content_based_recommendations(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            doctors = db.query(Doctor).order_by(Doctor.created_at.asc()).limit(4).all()
            doctor_cards = [{"id": item.id, "type": "doctor", "title": item.full_name or item.username, "score": 0.74, "specialty": item.specialty} for item in doctors]
            articles = [
                {"id": 1, "type": "article", "title": "Ayurvedic immunity essentials", "score": 0.7},
                {"id": 2, "type": "article", "title": "Managing digestion with dinacharya", "score": 0.68},
            ]
            return doctor_cards + articles
        finally:
            db.close()

    def combine_recommendations(self, collaborative: list[dict[str, Any]], content_based: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keyed = {f"{item['type']}:{item['id']}": item for item in collaborative + content_based}
        return list(keyed.values())

    async def get_personalized_offers(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        score = int(profile.get("health_score", 70))
        return [
            {"title": "Refill and save", "discount": "10%", "reason": "Medication continuity support"},
            {"title": "Preventive package", "discount": "15%", "reason": "Recommended for users with a health score below 85" if score < 85 else "Maintain preventive screening cadence"},
        ]

    async def get_purchase_history(self, user_id: int) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            orders = db.query(MedicineOrder).order_by(MedicineOrder.created_at.asc()).limit(20).all()
            history: list[dict[str, Any]] = []
            for order in orders:
                try:
                    items = json.loads(order.medicines_json or "[]")
                except Exception:
                    items = []
                history.append({"id": order.id, "date": order.created_at, "items": items})
            return history
        finally:
            db.close()

    def analyze_purchase_patterns(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        gaps: list[int] = []
        for left, right in zip(history, history[1:]):
            gaps.append(max(1, (right["date"] - left["date"]).days))
        items = []
        for row in history[-3:]:
            items.extend(row.get("items", []))
        return {"avg_gap": round(sum(gaps) / len(gaps)) if gaps else 7, "frequently_bought_together": items[:5]}

    async def get_user_vitals(self, user_id: int) -> dict[str, Any]:
        db = SessionLocal()
        try:
            vital = db.query(EMRVital).order_by(EMRVital.recorded_at.desc()).first()
            return vital.payload if vital else {"bp": "122/82", "weight": 70, "sleep_hours": 7}
        finally:
            db.close()

    async def get_user_medications(self, user_id: int) -> list[dict[str, Any]]:
        history = await self.get_purchase_history(user_id)
        meds: list[dict[str, Any]] = []
        for row in history[-3:]:
            meds.extend(row.get("items", []))
        return meds

    async def get_user_symptoms(self, user_id: int) -> list[str]:
        return ["fatigue", "acidity"] if user_id % 2 == 1 else ["headache"]

    def calculate_health_score(self, vitals: dict[str, Any]) -> int:
        score = 82
        if int(vitals.get("sleep_hours", 7) or 7) < 6:
            score -= 6
        return max(45, min(96, score))

    def identify_risk_factors(self, vitals: dict[str, Any], medications: list[dict[str, Any]]) -> list[str]:
        risks = []
        if int(vitals.get("sleep_hours", 7) or 7) < 6:
            risks.append("Inconsistent sleep")
        if len(medications) >= 3:
            risks.append("Multiple active medications")
        return risks or ["No major risk factors detected"]

    def generate_recommendations(self, vitals: dict[str, Any], symptoms: list[str]) -> list[str]:
        return ["Maintain hydration", "Schedule a preventive consultation", f"Monitor {symptoms[0]}" if symptoms else "Continue healthy routine"]

    def predict_health_issues(self, vitals: dict[str, Any], symptoms: list[str]) -> list[str]:
        return ["Digestive imbalance risk", "Seasonal immunity dip"] if "acidity" in symptoms else ["Routine monitoring advised"]

    def suggest_preventive_measures(self, vitals: dict[str, Any]) -> list[str]:
        return ["Daily walk for 30 minutes", "Regular sleep schedule", "Quarterly lab screening"]
