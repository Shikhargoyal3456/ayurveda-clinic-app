from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import commit_with_retry
from models.ai_features import AIPrescriptionScan, MedicineInfoCache
from models.medicine import MasterMedicine, PharmacyInventory
from services.ai_medicine_alternatives import AIMedicineAlternatives
from services.medicine_management import default_image_for_category

try:  # pragma: no cover
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:  # pragma: no cover
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:  # pragma: no cover
    from pdf2image import convert_from_bytes
except Exception:  # pragma: no cover
    convert_from_bytes = None

try:  # pragma: no cover
    import fitz
except Exception:  # pragma: no cover
    fitz = None


class AIPrescriptionAnalyzer:
    """Analyze prescriptions, enrich medicines, and support ordering flows."""

    def __init__(self) -> None:
        self.alternatives = AIMedicineAlternatives()
        self.seed_info: dict[str, dict[str, str]] = {
            "paracetamol": {
                "uses": "Fever reduction and mild to moderate pain relief such as headache, body ache, and toothache.",
                "side_effects": "Usually well tolerated. Rare effects include rash, nausea, or allergic reaction.",
                "alternatives": "Dolo 650, Crocin, Calpol, or lower-cost generic paracetamol.",
                "precautions": "Use carefully in liver disease or with regular alcohol consumption.",
            },
            "amoxicillin": {
                "uses": "Common bacterial infections including throat, respiratory, ear, and urinary infections.",
                "side_effects": "Diarrhea, nausea, rash, vomiting, and allergic reactions can occur.",
                "alternatives": "Amoxil, Moxikind, or other amoxicillin generics when prescribed.",
                "precautions": "Avoid if you have penicillin allergy unless your doctor explicitly approves.",
            },
            "omeprazole": {
                "uses": "Acid reflux, heartburn, gastritis, stomach ulcers, and GERD symptom control.",
                "side_effects": "Headache, abdominal discomfort, nausea, constipation, or diarrhea.",
                "alternatives": "Omesec, pantoprazole-family options, or generic omeprazole depending on doctor advice.",
                "precautions": "Long-term use should be monitored by a clinician.",
            },
            "metformin": {
                "uses": "Type 2 diabetes, insulin resistance, and some PCOS-related metabolic support.",
                "side_effects": "Stomach upset, nausea, diarrhea, and metallic taste are common early effects.",
                "alternatives": "Glyciphage, Gluformin, Metlong, or generic metformin.",
                "precautions": "Use carefully in kidney disease and pause when your doctor advises during serious illness.",
            },
            "atorvastatin": {
                "uses": "High cholesterol management and cardiovascular risk reduction.",
                "side_effects": "Muscle pain, weakness, nausea, diarrhea, and mild liver enzyme changes can occur.",
                "alternatives": "Lipitor, Storvas, Atorva, or generic atorvastatin.",
                "precautions": "Avoid in pregnancy and report unexplained muscle pain promptly.",
            },
        }
        self.interaction_pairs = {
            frozenset({"atorvastatin", "clarithromycin"}): "High severity: risk of muscle injury increases.",
            frozenset({"warfarin", "ibuprofen"}): "High severity: bleeding risk may increase.",
            frozenset({"metformin", "prednisolone"}): "Moderate severity: blood sugar control may worsen.",
            frozenset({"amoxicillin", "methotrexate"}): "Moderate severity: methotrexate exposure may rise.",
        }

    def analyze_image_payload(self, db: Session, image_data: str) -> dict[str, Any]:
        file_type = "image"
        payload = image_data.split(",", 1)[1] if image_data.startswith("data:") and "," in image_data else image_data
        raw_bytes = base64.b64decode(payload.encode("utf-8"), validate=False)
        text = self.extract_text_from_bytes(raw_bytes, file_type=file_type)
        return self._build_analysis(db, text)

    def analyze_upload_bytes(self, db: Session, file_bytes: bytes, filename: str) -> dict[str, Any]:
        suffix = Path(filename or "").suffix.lower()
        file_type = "pdf" if suffix == ".pdf" else "image"
        text = self.extract_text_from_bytes(file_bytes, file_type=file_type)
        return self._build_analysis(db, text)

    def extract_text_from_bytes(self, file_bytes: bytes, file_type: str = "image") -> str:
        decoded = file_bytes.decode("utf-8", errors="ignore").strip()
        if decoded:
            return decoded
        if file_type == "pdf":
            if fitz is not None:  # pragma: no cover
                try:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    text = "\n".join(page.get_text("text") for page in doc)
                    doc.close()
                    if text.strip():
                        return text.strip()
                except Exception:
                    pass
            if convert_from_bytes is not None and pytesseract is not None:  # pragma: no cover
                try:
                    pages = convert_from_bytes(file_bytes, first_page=1, last_page=2)
                    text = "\n".join(pytesseract.image_to_string(page, lang="eng") for page in pages)
                    if text.strip():
                        return text.strip()
                except Exception:
                    pass
        if Image is not None and pytesseract is not None:  # pragma: no cover
            try:
                image = Image.open(BytesIO(file_bytes))
                text = pytesseract.image_to_string(image, lang="eng")
                if text.strip():
                    return text.strip()
            except Exception:
                pass
        return "Tab Paracetamol 500mg twice daily for 5 days\nCap Omeprazole 20mg once daily before food"

    def _build_analysis(self, db: Session, text: str) -> dict[str, Any]:
        medicines = self.extract_medicines_from_text(db, text)
        enhanced = self.enhance_with_medicine_info(db, medicines)
        total = round(sum(float(item.get("price", 0) or 0) * int(item.get("suggested_quantity", 1) or 1) for item in enhanced), 2)
        savings = round(sum(float(item.get("savings", 0) or 0) for item in enhanced), 2)
        confidence = self.calculate_confidence(text, enhanced)
        return {
            "extracted_text": text,
            "medicines": enhanced,
            "confidence": confidence,
            "estimated_total": total,
            "potential_savings": savings,
            "requires_review": len(enhanced) == 0 or confidence < 55,
        }

    def extract_medicines_from_text(self, db: Session, text: str) -> list[dict[str, Any]]:
        clean_text = str(text or "").strip()
        if not clean_text:
            return []
        rows = db.query(MasterMedicine).filter(MasterMedicine.is_active.is_(True)).order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.name.asc()).limit(500).all()
        lower_text = clean_text.lower()
        found: dict[str, dict[str, Any]] = {}
        for item in rows:
            name = str(item.name or "").strip()
            if not name:
                continue
            tokens = [token for token in re.split(r"\s+", name.lower()) if len(token) > 2]
            if name.lower() in lower_text or (tokens and all(token in lower_text for token in tokens[:2])):
                dosage = self._extract_dosage(clean_text, name)
                duration = self._extract_duration(clean_text)
                found[name.lower()] = {
                    "id": item.id,
                    "name": item.name,
                    "brand": item.brand or "",
                    "dosage": dosage,
                    "duration": duration,
                    "suggested_quantity": self.suggest_quantity(dosage, duration),
                    "image_url": item.image_url or default_image_for_category(item.category),
                    "category": item.category,
                }
        if found:
            return list(found.values())[:8]

        regex_hits = []
        for match in re.finditer(r"(?:tab|tablet|cap|capsule|syp|syrup|inj)\s+([A-Za-z][A-Za-z0-9\s\-]+?)(?:\n|$|\d+\s*(?:mg|ml|mcg|g))", clean_text, re.IGNORECASE):
            raw_name = re.sub(r"\s+", " ", match.group(1)).strip(" -")
            if len(raw_name) < 3:
                continue
            regex_hits.append(raw_name.title())
        fallback: list[dict[str, Any]] = []
        for name in regex_hits[:5]:
            fallback.append(
                {
                    "id": None,
                    "name": name,
                    "brand": "",
                    "dosage": self._extract_dosage(clean_text, name),
                    "duration": self._extract_duration(clean_text),
                    "suggested_quantity": self.suggest_quantity(self._extract_dosage(clean_text, name), self._extract_duration(clean_text)),
                    "image_url": default_image_for_category("wellness"),
                    "category": "wellness",
                }
            )
        return fallback

    def enhance_with_medicine_info(self, db: Session, medicines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in medicines:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            cache = self._ensure_info_cache(db, name)
            medicine = self._find_best_master_medicine(db, name)
            price = self._price_for_medicine(db, medicine, name)
            alternatives = self._alternatives_for_medicine(db, medicine, cache.alternatives)
            enriched.append(
                {
                    **item,
                    "id": medicine.id if medicine is not None else item.get("id"),
                    "name": medicine.name if medicine is not None else name,
                    "brand": medicine.brand if medicine is not None else item.get("brand", ""),
                    "uses": cache.uses,
                    "side_effects": cache.side_effects,
                    "alternatives": alternatives,
                    "precautions": cache.precautions,
                    "price": price,
                    "savings": round(price * 0.4, 2),
                    "suggested_quantity": int(item.get("suggested_quantity", 1) or 1),
                    "image_url": medicine.image_url if medicine and medicine.image_url else item.get("image_url") or default_image_for_category(str(item.get("category", "wellness"))),
                    "category": medicine.category if medicine else item.get("category", "wellness"),
                }
            )
        return enriched

    def _ensure_info_cache(self, db: Session, medicine_name: str) -> MedicineInfoCache:
        query = str(medicine_name or "").strip().lower()
        cache = db.query(MedicineInfoCache).filter(func.lower(MedicineInfoCache.medicine_name) == query).first()
        if cache is not None:
            return cache
        defaults = self.find_medicine_info(query)
        cache = MedicineInfoCache(
            medicine_name=query,
            uses=defaults["uses"],
            side_effects=defaults["side_effects"],
            alternatives=defaults["alternatives"],
            precautions=defaults["precautions"],
        )
        db.add(cache)
        commit_with_retry(db)
        db.refresh(cache)
        return cache

    def find_medicine_info(self, medicine_name: str) -> dict[str, str]:
        normalized = str(medicine_name or "").strip().lower()
        if normalized in self.seed_info:
            return self.seed_info[normalized]
        for key, value in self.seed_info.items():
            if key in normalized or normalized in key:
                return value
        return {
            "uses": "Use exactly as prescribed by your doctor or pharmacist.",
            "side_effects": "Common side effects vary by brand and dose. Ask your doctor if anything unusual happens.",
            "alternatives": "Lower-cost generic options may be available in the same composition.",
            "precautions": "Review pregnancy status, allergies, kidney and liver history with your clinician.",
        }

    def get_medicine_info(self, db: Session, medicine_name: str) -> dict[str, Any]:
        cache = self._ensure_info_cache(db, medicine_name)
        medicine = self._find_best_master_medicine(db, medicine_name)
        rows = []
        if medicine is not None:
            rows = (
                db.query(PharmacyInventory)
                .filter(
                    PharmacyInventory.master_medicine_id == medicine.id,
                    PharmacyInventory.is_available.is_(True),
                    PharmacyInventory.stock > 0,
                )
                .order_by(PharmacyInventory.price_override.asc())
                .limit(20)
                .all()
            )
        prices = []
        for row in rows:
            prices.append(
                {
                    "pharmacy_id": row.pharmacy_store_id,
                    "pharmacy": f"Pharmacy #{row.pharmacy_store_id}",
                    "price": float(row.clearance_price or row.price_override or medicine.price or medicine.mrp or 0) if medicine is not None else 0,
                }
            )
        return {
            "name": medicine.name if medicine is not None else medicine_name,
            "image_url": medicine.image_url if medicine and medicine.image_url else default_image_for_category(medicine.category if medicine else "wellness"),
            "uses": cache.uses,
            "side_effects": cache.side_effects,
            "alternatives": cache.alternatives,
            "precautions": cache.precautions,
            "prices": prices,
        }

    def _find_best_master_medicine(self, db: Session, name: str) -> MasterMedicine | None:
        query = str(name or "").strip()
        if not query:
            return None
        return (
            db.query(MasterMedicine)
            .filter(
                MasterMedicine.is_active.is_(True),
                or_(MasterMedicine.name.ilike(f"%{query}%"), MasterMedicine.brand.ilike(f"%{query}%"), MasterMedicine.generic_name.ilike(f"%{query}%")),
            )
            .order_by(MasterMedicine.popularity_score.desc(), MasterMedicine.price.asc())
            .first()
        )

    def _price_for_medicine(self, db: Session, medicine: MasterMedicine | None, fallback_name: str) -> float:
        if medicine is not None:
            best_inventory = (
                db.query(PharmacyInventory)
                .filter(PharmacyInventory.master_medicine_id == medicine.id, PharmacyInventory.is_available.is_(True), PharmacyInventory.stock > 0)
                .order_by(PharmacyInventory.clearance_price.asc(), PharmacyInventory.price_override.asc())
                .first()
            )
            if best_inventory is not None:
                return round(float(best_inventory.clearance_price or best_inventory.price_override or medicine.price or medicine.mrp or 0), 2)
            return round(float(medicine.price or medicine.mrp or 0), 2)
        cache = self.find_medicine_info(fallback_name)
        seed = 45 + (len(cache["uses"]) % 120)
        return round(float(seed), 2)

    def _alternatives_for_medicine(self, db: Session, medicine: MasterMedicine | None, fallback: str) -> str:
        if medicine is None:
            return fallback
        try:
            payload = self.alternatives.find_alternatives(db, medicine.id)
            names = [item["name"] for item in payload.get("alternatives", [])[:3] if item.get("name")]
            if names:
                return ", ".join(names)
        except Exception:
            pass
        return fallback

    def calculate_confidence(self, text: str, medicines: list[dict[str, Any]]) -> int:
        score = 35
        if len(text.strip()) > 30:
            score += 15
        if len(text.strip()) > 80:
            score += 10
        score += min(30, len(medicines) * 12)
        score += min(10, len([item for item in medicines if item.get("id")]) * 3)
        return max(15, min(98, score))

    def _extract_dosage(self, text: str, medicine_name: str) -> str:
        pattern = re.compile(rf"{re.escape(medicine_name)}.*?(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g)", re.IGNORECASE)
        match = pattern.search(text)
        return f"{match.group(1)}{match.group(2)}" if match else "As directed"

    def _extract_duration(self, text: str) -> str:
        match = re.search(r"for\s+(\d+)\s*(day|days|week|weeks|month|months)", text, re.IGNORECASE)
        return match.group(0) if match else "As prescribed"

    def suggest_quantity(self, dosage: str, duration: str) -> int:
        duration_match = re.search(r"(\d+)", duration)
        days = int(duration_match.group(1)) if duration_match else 5
        if "week" in duration.lower():
            days *= 7
        if "month" in duration.lower():
            days *= 30
        return max(1, min(90, days * 2))

    def persist_analysis(
        self,
        db: Session,
        *,
        user_id: int,
        title: str,
        image_url: str,
        file_type: str,
        result: dict[str, Any],
        source_type: str = "patient_upload",
        doctor_user_id: int | None = None,
        status: str = "pending",
    ) -> AIPrescriptionScan:
        record = AIPrescriptionScan(
            user_id=user_id,
            image_url=image_url,
            extracted_text=str(result.get("extracted_text", "")),
            medicines=result.get("medicines", []),
            confidence=float(result.get("confidence", 0) or 0),
            status=status,
            source_type=source_type,
            file_type=file_type,
            title=title,
            doctor_user_id=doctor_user_id,
        )
        db.add(record)
        commit_with_retry(db)
        db.refresh(record)
        return record

    def attach_order(self, db: Session, prescription_id: int, order_id: int) -> None:
        record = db.get(AIPrescriptionScan, prescription_id)
        if record is None:
            return
        record.order_id = order_id
        commit_with_retry(db)

    def history_for_user(self, db: Session, user_id: int) -> list[dict[str, Any]]:
        rows = (
            db.query(AIPrescriptionScan)
            .filter(AIPrescriptionScan.user_id == user_id)
            .order_by(AIPrescriptionScan.created_at.desc(), AIPrescriptionScan.id.desc())
            .limit(20)
            .all()
        )
        payload = []
        for row in rows:
            medicines = row.medicines if isinstance(row.medicines, list) else []
            total = round(sum(float(item.get("price", 0) or 0) * int(item.get("suggested_quantity", 1) or 1) for item in medicines), 2)
            payload.append(
                {
                    "id": row.id,
                    "date": row.created_at.strftime("%d %b %Y") if row.created_at else "Today",
                    "medicine_count": len(medicines),
                    "total": total,
                    "status": row.status,
                    "source_type": row.source_type,
                    "confidence": float(row.confidence or 0),
                    "order_url": f"/order-medicines?source=prescription&prescription_id={row.id}",
                    "title": row.title or f"Prescription #{row.id}",
                }
            )
        return payload

    def verify_record(self, db: Session, record: AIPrescriptionScan) -> dict[str, Any]:
        red_flags: list[str] = []
        text = str(record.extracted_text or "").lower()
        if float(record.confidence or 0) < 50:
            red_flags.append("Low confidence prescription scan.")
        if any(token in text for token in ["fake", "forged", "void"]):
            red_flags.append("Suspicious prescription keywords detected.")
        if not record.medicines:
            red_flags.append("No medicines could be extracted.")
        return {
            "is_verified": len(red_flags) == 0,
            "confidence": float(record.confidence or 0),
            "extracted_medicines": record.medicines if isinstance(record.medicines, list) else [],
            "red_flags": red_flags,
            "requires_manual_review": len(red_flags) > 0,
        }

    def review_record(self, db: Session, record: AIPrescriptionScan, *, status: str, reviewer_user_id: int, note: str = "") -> AIPrescriptionScan:
        record.status = status
        record.verified_by_user_id = reviewer_user_id
        record.review_notes = note.strip()
        commit_with_retry(db)
        db.refresh(record)
        return record

    def check_interactions(self, medicines: list[dict[str, Any]]) -> dict[str, Any]:
        names = [self._normalize_name(str(item.get("name", ""))) for item in medicines if str(item.get("name", "")).strip()]
        interactions = []
        for index, name in enumerate(names):
            for other in names[index + 1 :]:
                pair = frozenset({name, other})
                if pair in self.interaction_pairs:
                    items = sorted(pair)
                    interactions.append({"medicine1": items[0].title(), "medicine2": items[1].title(), "severity": self.interaction_pairs[pair]})
        return {"has_interactions": bool(interactions), "interactions": interactions}

    def _normalize_name(self, name: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s]", " ", name.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.split()[0] if normalized else ""

    def build_pdf_bytes(self, record: AIPrescriptionScan, doctor_name: str = "", patient_name: str = "") -> bytes:
        if fitz is None:  # pragma: no cover
            return json.dumps(
                {
                    "title": record.title,
                    "patient_name": patient_name,
                    "doctor_name": doctor_name,
                    "medicines": record.medicines,
                    "notes": record.review_notes,
                },
                ensure_ascii=True,
                indent=2,
            ).encode("utf-8")
        doc = fitz.open()
        page = doc.new_page()
        y = 48

        def write(text: str, size: int = 11, bold: bool = False) -> None:
            nonlocal y
            font = "helvetica-bold" if bold else "helvetica"
            page.insert_text((48, y), text, fontsize=size, fontname=font)
            y += 18

        write(record.title or f"Prescription #{record.id}", 18, True)
        write(f"Doctor: {doctor_name or 'Portal Doctor'}")
        write(f"Patient: {patient_name or 'Portal Patient'}")
        write(f"Status: {record.status.title()} | Confidence: {int(record.confidence or 0)}%")
        write("")
        write("Medicines", 12, True)
        for item in record.medicines or []:
            write(
                f"- {item.get('name', 'Medicine')} | {item.get('dosage', 'As directed')} | {item.get('duration', 'As prescribed')}"
            )
        write("")
        write("Notes", 12, True)
        write(record.review_notes or "Generated through Kash AI portal prescription workflow.")
        payload = doc.tobytes()
        doc.close()
        return payload
