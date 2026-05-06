from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.medicine import MasterMedicine


class AIMedicineAlternatives:
    """Suggest generic, therapeutic, and Ayurveda alternatives."""

    ayurvedic_mapping = {
        "paracetamol": "Giloy",
        "omeprazole": "Amalaki",
        "metformin": "Karela",
        "amoxicillin": "Neem",
        "cetirizine": "Haridra",
    }

    def extract_active_ingredient(self, name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", str(name or "")).strip().lower()
        tokens = [token for token in cleaned.split() if token and not token.isdigit()]
        return tokens[0] if tokens else cleaned

    def find_alternatives(self, db: Session, medicine_id: int) -> dict[str, Any]:
        medicine = db.get(MasterMedicine, medicine_id)
        if medicine is None:
            raise ValueError("Medicine not found")
        alternatives = []
        alternatives.extend(self.find_generic_alternatives(db, medicine))
        alternatives.extend(self.find_therapeutic_alternatives(db, medicine))
        if medicine.category == "allopathy":
            alternatives.extend(self.find_ayurvedic_alternatives(db, medicine))

        unique: list[dict[str, Any]] = []
        seen: set[int] = set()
        current_price = float(medicine.price or medicine.mrp or 0)
        for alt in alternatives:
            if alt["id"] in seen:
                continue
            seen.add(alt["id"])
            alt["original_price"] = current_price
            alt["savings"] = max(0, round(current_price - float(alt["price"]), 2))
            alt["savings_percent"] = round((alt["savings"] / current_price) * 100, 1) if current_price > 0 else 0
            unique.append(alt)
        unique.sort(key=lambda item: (item["savings"], item["price"]), reverse=True)
        return {
            "original": {
                "id": medicine.id,
                "name": medicine.name,
                "brand": medicine.brand or "",
                "price": current_price,
            },
            "alternatives": unique[:5],
            "max_savings_percent": max((item["savings_percent"] for item in unique), default=0),
        }

    def find_alternatives_by_name(self, db: Session, medicine_name: str) -> dict[str, Any]:
        query = str(medicine_name or "").strip()
        if not query:
            raise ValueError("Medicine name is required")
        medicine = (
            db.query(MasterMedicine)
            .filter(
                MasterMedicine.is_active.is_(True),
                or_(MasterMedicine.name.ilike(f"%{query}%"), MasterMedicine.brand.ilike(f"%{query}%")),
            )
            .order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.price.asc())
            .first()
        )
        if medicine is None:
            raise ValueError("Medicine not found")
        return self.find_alternatives(db, medicine.id)

    def find_generic_alternatives(self, db: Session, medicine: MasterMedicine) -> list[dict[str, Any]]:
        ingredient = self.extract_active_ingredient(medicine.generic_name or medicine.name)
        rows = (
            db.query(MasterMedicine)
            .filter(
                MasterMedicine.id != medicine.id,
                MasterMedicine.is_active.is_(True),
                MasterMedicine.category == medicine.category,
                or_(MasterMedicine.name.ilike(f"%{ingredient}%"), MasterMedicine.generic_name.ilike(f"%{ingredient}%")),
            )
            .order_by(MasterMedicine.price.asc(), MasterMedicine.popularity_score.desc())
            .limit(5)
            .all()
        )
        return [self._payload(item, "Same active ingredient / generic match") for item in rows]

    def find_therapeutic_alternatives(self, db: Session, medicine: MasterMedicine) -> list[dict[str, Any]]:
        rows = (
            db.query(MasterMedicine)
            .filter(
                MasterMedicine.id != medicine.id,
                MasterMedicine.is_active.is_(True),
                MasterMedicine.category == medicine.category,
            )
            .order_by(MasterMedicine.price.asc(), MasterMedicine.popularity_score.desc())
            .limit(5)
            .all()
        )
        return [self._payload(item, "Same therapy category alternative") for item in rows]

    def find_ayurvedic_alternatives(self, db: Session, medicine: MasterMedicine) -> list[dict[str, Any]]:
        ingredient = self.extract_active_ingredient(medicine.generic_name or medicine.name)
        mapped = self.ayurvedic_mapping.get(ingredient.lower())
        if not mapped:
            return []
        rows = (
            db.query(MasterMedicine)
            .filter(
                MasterMedicine.id != medicine.id,
                MasterMedicine.is_active.is_(True),
                MasterMedicine.category == "ayurveda",
                MasterMedicine.name.ilike(f"%{mapped}%"),
            )
            .order_by(MasterMedicine.price.asc(), MasterMedicine.popularity_score.desc())
            .limit(3)
            .all()
        )
        return [self._payload(item, "Ayurvedic support alternative") for item in rows]

    def _payload(self, item: MasterMedicine, reason: str) -> dict[str, Any]:
        return {
            "id": item.id,
            "name": item.name,
            "brand": item.brand or "",
            "price": float(item.price or item.mrp or 0),
            "category": item.category,
            "rating": 4.5,
            "similarity_reason": reason,
        }
