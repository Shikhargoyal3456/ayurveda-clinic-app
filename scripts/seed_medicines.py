#!/usr/bin/env python
"""
Seed medicines into the database.
Run: python scripts/seed_medicines.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "ayurveda.db"

MEDICINES = [
    {"name": "Paracetamol 500mg", "brand": "Cipla", "category": "allopathy", "mrp": 50, "price": 35, "stock": 100, "prescription_required": 0, "description": "General symptom support"},
    {"name": "Dolo 650", "brand": "Micro Labs", "category": "allopathy", "mrp": 58, "price": 42, "stock": 150, "prescription_required": 0, "description": "Fever and headache relief"},
    {"name": "Amoxicillin 250mg", "brand": "Alkem", "category": "allopathy", "mrp": 120, "price": 85, "stock": 50, "prescription_required": 1, "description": "Antibiotic for bacterial infections"},
    {"name": "Azithromycin 500mg", "brand": "Cipla", "category": "allopathy", "mrp": 180, "price": 140, "stock": 30, "prescription_required": 1, "description": "Bacterial infection treatment"},
    {"name": "Cetirizine 10mg", "brand": "Glaxo", "category": "allopathy", "mrp": 45, "price": 32, "stock": 120, "prescription_required": 0, "description": "Allergy relief"},
    {"name": "Metformin 500mg", "brand": "USV", "category": "allopathy", "mrp": 35, "price": 25, "stock": 80, "prescription_required": 1, "description": "Diabetes management"},
    {"name": "Omeprazole 20mg", "brand": "Cipla", "category": "allopathy", "mrp": 60, "price": 45, "stock": 90, "prescription_required": 0, "description": "Acid reflux treatment"},
    {"name": "Amlodipine 5mg", "brand": "Pfizer", "category": "allopathy", "mrp": 45, "price": 32, "stock": 70, "prescription_required": 1, "description": "High blood pressure"},
    {"name": "Atorvastatin 10mg", "brand": "Pfizer", "category": "allopathy", "mrp": 90, "price": 65, "stock": 60, "prescription_required": 1, "description": "Cholesterol management"},
    {"name": "Ashwagandha Capsules", "brand": "Himalaya", "category": "ayurveda", "mrp": 350, "price": 299, "stock": 80, "prescription_required": 0, "description": "Stress relief and immunity"},
    {"name": "Chyawanprash", "brand": "Dabur", "category": "ayurveda", "mrp": 450, "price": 399, "stock": 50, "prescription_required": 0, "description": "Ayurvedic immunity booster"},
    {"name": "Triphala Tablets", "brand": "Baidyanath", "category": "ayurveda", "mrp": 120, "price": 99, "stock": 100, "prescription_required": 0, "description": "Digestive health"},
    {"name": "Giloy Juice", "brand": "Patanjali", "category": "ayurveda", "mrp": 180, "price": 150, "stock": 60, "prescription_required": 0, "description": "Immunity booster"},
    {"name": "Tulsi Drops", "brand": "Himalaya", "category": "ayurveda", "mrp": 95, "price": 79, "stock": 100, "prescription_required": 0, "description": "Respiratory health"},
    {"name": "Brahmi Capsules", "brand": "Himalaya", "category": "ayurveda", "mrp": 280, "price": 239, "stock": 70, "prescription_required": 0, "description": "Memory and stress"},
    {"name": "Vitamin D3 60K", "brand": "Healthcare", "category": "wellness", "mrp": 180, "price": 150, "stock": 100, "prescription_required": 0, "description": "Bone health supplement"},
    {"name": "Calcium + Vitamin D3", "brand": "Supradyn", "category": "wellness", "mrp": 220, "price": 185, "stock": 80, "prescription_required": 0, "description": "Bone and joint health"},
    {"name": "Omega 3 Capsules", "brand": "Seven Seas", "category": "wellness", "mrp": 450, "price": 380, "stock": 40, "prescription_required": 0, "description": "Heart and brain health"},
    {"name": "Protein Powder", "brand": "MuscleBlaze", "category": "wellness", "mrp": 2500, "price": 1999, "stock": 30, "prescription_required": 0, "description": "Muscle growth and recovery"},
]


def seed_medicines() -> int:
    """Add medicines to database if the master catalog is empty."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medicines_master'")
        if not cursor.fetchone():
            print("medicines_master table does not exist. Run migrations first.")
            return 1

        cursor.execute("SELECT COUNT(*) FROM medicines_master")
        existing_count = int(cursor.fetchone()[0] or 0)
        if existing_count > 0:
            print(f"Catalog already has {existing_count} medicines. Skipping seed.")
            return 0

        inserted = 0
        for med in MEDICINES:
            try:
                cursor.execute(
                    """
                    INSERT INTO medicines_master
                    (name, brand, category, mrp, price, prescription_required, description, popularity_score, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """,
                    (
                        med["name"],
                        med["brand"],
                        med["category"],
                        med["mrp"],
                        med["price"],
                        med["prescription_required"],
                        med["description"],
                        int(med["stock"]),
                    ),
                )
                inserted += 1
            except Exception as exc:
                print(f"Failed to insert {med['name']}: {exc}")

        conn.commit()
        print(f"Added {inserted} medicines to catalog.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(seed_medicines())
