"""Idempotent Demo Data & User Seeding Script.

Run this script once to populate default admin, doctor, and patient demo accounts,
along with sample patients, case sheets, prescriptions, and clinic metrics.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Ensure app root is in sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db, commit_with_retry
from app.models import Doctor
from app.auth import hash_password
from app.demo_seed import create_demo_data


def seed_demo_users_and_data() -> None:
    init_db()
    db: Session = SessionLocal()
    try:
        print("[+] Seeding Demo Users & Clinic Data...")

        # 1. Seed Demo Doctor
        doctor = db.query(Doctor).filter(Doctor.username == "dr_demo").first()
        if not doctor:
            doctor = Doctor(
                username="dr_demo",
                full_name="Dr. Ananya Sharma",
                specialty="ayurveda",
                password_hash=hash_password("password123"),
            )
            db.add(doctor)
            db.flush()
            print("  [*] Created Demo Doctor: dr_demo / password123")
        else:
            print("  [-] Demo Doctor (dr_demo) already exists.")

        # 2. Seed Default Admin Doctor
        admin_doc = db.query(Doctor).filter(Doctor.username == "admin").first()
        if not admin_doc:
            admin_doc = Doctor(
                username="admin",
                full_name="Clinic Administrator",
                specialty="ayurveda_admin",
                password_hash=hash_password("admin123"),
            )
            db.add(admin_doc)
            db.flush()
            print("  [*] Created Admin Account: admin / admin123")
        else:
            print("  [-] Admin Account (admin) already exists.")

        commit_with_retry(db)

        # 3. Seed Demo Patients, Prescriptions, and Appointments
        result = create_demo_data(db, doctor)
        print(f"  [*] Seeded Demo Patients & Prescriptions: {result}")

        print("[+] Demo seeding complete! Data is ready for use.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users_and_data()
