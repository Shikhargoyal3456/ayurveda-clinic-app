from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, init_db
from app.models import Hospital


SAMPLE_HOSPITALS = [
    {"name": "Apollo Hospital", "city": "Jaipur", "bed_capacity": 200, "available_beds": 45},
    {"name": "Fortis Hospital", "city": "Jaipur", "bed_capacity": 150, "available_beds": 12},
    {"name": "SMS Hospital", "city": "Jaipur", "bed_capacity": 500, "available_beds": 78},
    {"name": "AIIMS Jodhpur", "city": "Jodhpur", "bed_capacity": 350, "available_beds": 95},
    {"name": "Narayana Hospital", "city": "Jaipur", "bed_capacity": 120, "available_beds": 8},
]


def seed_hospitals() -> int:
    init_db()
    db = SessionLocal()
    inserted = 0
    try:
        for sample in SAMPLE_HOSPITALS:
            exists = db.query(Hospital.id).filter(
                Hospital.name == sample["name"], Hospital.city == sample["city"]
            ).first()
            if exists:
                continue
            db.add(
                Hospital(
                    **sample,
                    address=f"{sample['city']}, Rajasthan",
                    emergency_available=True,
                )
            )
            inserted += 1
        db.commit()
        return inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Hospital seed complete: {seed_hospitals()} sample hospitals added.")
