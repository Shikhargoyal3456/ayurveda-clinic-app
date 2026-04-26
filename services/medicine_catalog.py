from __future__ import annotations

from typing import Any

from app.database import SessionLocal, commit_with_retry
from models.medicine import Medicine, Pharmacy


# GRAND-UNIFIED-1: Production-friendly default catalog with 20+ staples and prices.
DEFAULT_MEDICINES: list[dict[str, Any]] = [
    {"name": "Ashwagandha", "system": "ayurveda", "category": "wellness", "price": 299, "unit": "60 tablets", "otc": True, "stock": 30},
    {"name": "Triphala", "system": "ayurveda", "category": "digestion", "price": 199, "unit": "100 g", "otc": True, "stock": 40},
    {"name": "Amla Juice", "system": "ayurveda", "category": "immunity", "price": 399, "unit": "1 bottle", "otc": True, "stock": 25},
    {"name": "Chyawanprash", "system": "ayurveda", "category": "immunity", "price": 349, "unit": "500 g", "otc": True, "stock": 35},
    {"name": "Giloy Tablet", "system": "ayurveda", "category": "immunity", "price": 249, "unit": "60 tablets", "otc": True, "stock": 30},
    {"name": "Tulsi Drops", "system": "ayurveda", "category": "cold_cough", "price": 179, "unit": "30 ml", "otc": True, "stock": 45},
    {"name": "Neem Capsules", "system": "ayurveda", "category": "skin", "price": 229, "unit": "60 capsules", "otc": True, "stock": 20},
    {"name": "Brahmi Vati", "system": "ayurveda", "category": "wellness", "price": 289, "unit": "40 tablets", "otc": False, "stock": 15},
    {"name": "Shatavari Kalpa", "system": "ayurveda", "category": "wellness", "price": 449, "unit": "250 g", "otc": True, "stock": 20},
    {"name": "Dashmool Kwath", "system": "ayurveda", "category": "pain_relief", "price": 259, "unit": "200 ml", "otc": False, "stock": 12},
    {"name": "Sitopaladi Churna", "system": "ayurveda", "category": "cold_cough", "price": 149, "unit": "100 g", "otc": True, "stock": 50},
    {"name": "Avipattikar Churna", "system": "ayurveda", "category": "digestion", "price": 169, "unit": "100 g", "otc": True, "stock": 50},
    {"name": "Hingvastak Churna", "system": "ayurveda", "category": "digestion", "price": 159, "unit": "100 g", "otc": True, "stock": 35},
    {"name": "Mulethi Powder", "system": "ayurveda", "category": "cold_cough", "price": 139, "unit": "100 g", "otc": True, "stock": 25},
    {"name": "Haridra Tablet", "system": "ayurveda", "category": "skin", "price": 219, "unit": "60 tablets", "otc": True, "stock": 25},
    {"name": "Liv Support Syrup", "system": "ayurveda", "category": "wellness", "price": 199, "unit": "200 ml", "otc": True, "stock": 22},
    {"name": "Arnica 30", "system": "homeopathy", "category": "pain_relief", "price": 99, "unit": "30 ml", "otc": True, "stock": 30},
    {"name": "Chlorhexidine Mouthwash", "system": "dental", "category": "dental", "price": 149, "unit": "150 ml", "otc": True, "stock": 20},
    {"name": "Diclofenac Gel", "system": "physiotherapy", "category": "pain_relief", "price": 129, "unit": "30 g", "otc": True, "stock": 30},
    {"name": "Paracetamol", "system": "modern_medicine", "category": "pain_relief", "price": 35, "unit": "10 tablets", "otc": True, "stock": 100},
    {"name": "Ibuprofen", "system": "modern_medicine", "category": "pain_relief", "price": 55, "unit": "10 tablets", "otc": True, "stock": 50},
    {"name": "ORS Sachet", "system": "modern_medicine", "category": "digestion", "price": 25, "unit": "1 sachet", "otc": True, "stock": 60},
    {"name": "Vitamin C Tablet", "system": "modern_medicine", "category": "immunity", "price": 120, "unit": "15 tablets", "otc": True, "stock": 40},
]


def get_default_medicines() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_MEDICINES]


def seed_default_medicine_catalog() -> dict[str, int]:
    # GRAND-UNIFIED-1: Seed real DB catalog only when empty, preserving pharmacy/admin edits.
    db = SessionLocal()
    try:
        existing_count = db.query(Medicine).count()
        if existing_count:
            return {"seeded": 0, "existing": int(existing_count)}
        pharmacy = db.query(Pharmacy).filter(Pharmacy.is_active.is_(True)).order_by(Pharmacy.id.asc()).first()
        if pharmacy is None:
            pharmacy = Pharmacy(
                name="Kash AI Partner Pharmacy",
                address="Local partner pharmacy",
                city="Gurugram",
                pincode="122001",
                phone="9999999999",
                whatsapp_number="9999999999",
                lat="28.4595",
                lng="77.0266",
                drug_licence_number="DEV-SEED-001",
                is_active=True,
            )
            db.add(pharmacy)
            commit_with_retry(db)
            db.refresh(pharmacy)
        for item in DEFAULT_MEDICINES:
            db.add(
                Medicine(
                    name=item["name"],
                    generic_name=item["name"],
                    category=item["category"],
                    price=int(item["price"]),
                    unit=item["unit"],
                    requires_prescription=not bool(item["otc"]),
                    is_available=True,
                    pharmacy_id=pharmacy.id,
                )
            )
        commit_with_retry(db)
        return {"seeded": len(DEFAULT_MEDICINES), "existing": 0}
    except Exception:
        db.rollback()
        return {"seeded": 0, "existing": 0}
    finally:
        db.close()
