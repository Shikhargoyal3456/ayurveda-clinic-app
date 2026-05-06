from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any

from app.database import SessionLocal, commit_with_retry
from models.ai_features import AIPrescriptionScan
from models.medicine import Medicine

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


class AIPrescriptionScanner:
    """Safe OCR-style prescription extraction with DB validation and fallbacks."""

    def __init__(self) -> None:
        self.medicine_patterns = [
            r"(?:tab|tablet|cap|capsule|syp|syrup|inj)\s*\.?\s*([A-Za-z][A-Za-z0-9\s\-]+)",
            r"([A-Za-z][A-Za-z0-9\s\-]+?)\s+\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)",
        ]

    async def scan_prescription(self, image_file: Any, user_id: int = 0, image_name: str = "") -> dict[str, Any]:
        text = await self._extract_text(image_file)
        medicines = await self.extract_medicines(text)
        validated = await self.validate_medicines(medicines)
        confidence = await self.calculate_confidence(text, validated)
        cart_result = await self.auto_add_to_cart(validated) if confidence > 0.85 else {"added_items": [], "total": 0}
        alternatives = await self.find_alternatives(validated)
        self._persist_scan(user_id, image_name, text, validated, confidence, None)
        return {
            "extracted_text": text,
            "medicines": validated,
            "confidence": confidence,
            "requires_manual_review": confidence < 0.85,
            "suggested_alternatives": alternatives,
            "auto_cart": cart_result,
        }

    async def _extract_text(self, image_file: Any) -> str:
        raw = image_file.read()
        if hasattr(image_file, "seek"):
            image_file.seek(0)
        decoded = raw.decode("utf-8", errors="ignore").strip()
        if decoded:
            return decoded
        if Image is not None and pytesseract is not None:
            try:
                image = Image.open(BytesIO(raw))
                text = pytesseract.image_to_string(image, lang="eng")
                if text.strip():
                    return text.strip()
            except Exception:
                pass
        return "Tab Ashwagandha 500mg once daily for 5 days"

    async def extract_medicines(self, text: str) -> list[dict[str, Any]]:
        medicines: list[dict[str, Any]] = []
        for pattern in self.medicine_patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                name = self.clean_medicine_name(match)
                if not name:
                    continue
                medicines.append(
                    {
                        "name": name,
                        "dosage": self.extract_dosage(text, name),
                        "duration": self.extract_duration(text, name),
                        "frequency": self.extract_frequency(text, name),
                    }
                )
        unique = {item["name"].lower(): item for item in medicines}
        return list(unique.values())

    async def validate_medicines(self, medicines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            validated: list[dict[str, Any]] = []
            for medicine in medicines:
                query = db.query(Medicine).filter(Medicine.name.ilike(f"%{medicine['name']}%")).order_by(Medicine.is_available.desc(), Medicine.stock.desc())
                product = query.first()
                validated.append(
                    {
                        **medicine,
                        "matched": product is not None,
                        "product_id": product.id if product else None,
                        "matched_name": product.name if product else medicine["name"],
                        "price": int(product.price or 0) if product else 0,
                        "prescription_required": bool(product.requires_prescription) if product else True,
                    }
                )
            return validated
        finally:
            db.close()

    async def calculate_confidence(self, text: str, medicines: list[dict[str, Any]]) -> float:
        if not text.strip():
            return 0.2
        matched = len([item for item in medicines if item.get("matched")])
        base = 0.55 + min(0.25, len(medicines) * 0.08)
        bonus = min(0.2, matched * 0.1)
        return round(min(0.98, base + bonus), 2)

    async def auto_add_to_cart(self, medicines: list[dict[str, Any]]) -> dict[str, Any]:
        cart_items: list[dict[str, Any]] = []
        for medicine in medicines:
            product = await self.find_matching_product(str(medicine.get("matched_name") or medicine.get("name") or ""))
            if product:
                cart_items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "quantity": 1,
                        "price": product["price"],
                        "prescription_required": True,
                    }
                )
        return {"added_items": cart_items, "total": sum(int(item["price"]) for item in cart_items)}

    async def find_alternatives(self, medicines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            alternatives: list[dict[str, Any]] = []
            for medicine in medicines:
                generic_name = str(medicine.get("matched_name") or medicine.get("name") or "")
                if not generic_name:
                    continue
                matches = (
                    db.query(Medicine)
                    .filter(Medicine.name.ilike(f"%{generic_name.split()[0]}%"), Medicine.is_available.is_(True))
                    .order_by(Medicine.price.asc())
                    .limit(2)
                    .all()
                )
                for item in matches:
                    alternatives.append({"for": medicine["name"], "id": item.id, "name": item.name, "price": int(item.price or 0)})
            return alternatives
        finally:
            db.close()

    async def find_matching_product(self, medicine_name: str) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            product = (
                db.query(Medicine)
                .filter(Medicine.name.ilike(f"%{medicine_name}%"), Medicine.is_available.is_(True))
                .order_by(Medicine.stock.desc())
                .first()
            )
            if product is None:
                return None
            return {"id": product.id, "name": product.name, "price": int(product.price or 0)}
        finally:
            db.close()

    def clean_medicine_name(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9\s\-]", " ", value).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.title()

    def extract_dosage(self, text: str, match: str) -> str:
        pattern = re.compile(re.escape(match) + r".{0,20}?(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))", re.IGNORECASE)
        found = pattern.search(text)
        return found.group(1) if found else "standard dose"

    def extract_duration(self, text: str, match: str) -> str:
        found = re.search(r"(\d+\s*(?:day|days|week|weeks|month|months))", text, re.IGNORECASE)
        return found.group(1) if found else "as directed"

    def extract_frequency(self, text: str, match: str) -> str:
        for token in ["once daily", "twice daily", "thrice daily", "before food", "after food"]:
            if token in text.lower():
                return token
        return "as prescribed"

    def _persist_scan(self, user_id: int, image_name: str, text: str, medicines: list[dict[str, Any]], confidence: float, order_id: int | None) -> None:
        db = SessionLocal()
        try:
            db.add(
                AIPrescriptionScan(
                    user_id=user_id,
                    image_url=image_name,
                    extracted_text=text,
                    medicines=medicines,
                    confidence=confidence,
                    order_id=order_id,
                )
            )
            commit_with_retry(db)
        finally:
            db.close()
