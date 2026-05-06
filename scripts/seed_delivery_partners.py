from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_HTTPS_ONLY", "false")
os.environ.setdefault("HTTPS_REDIRECT_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("APP_ENV", "testing")

from app.database import SessionLocal, init_db  # noqa: E402
from models.marketplace import DeliveryPartner  # noqa: E402
from services.marketplace_service import ensure_marketplace_seed_data  # noqa: E402


def main() -> int:
    init_db()
    created = ensure_marketplace_seed_data()

    db = SessionLocal()
    try:
        partners = db.query(DeliveryPartner).order_by(DeliveryPartner.rating.desc()).all()
        print("Delivery partner seed complete.")
        print(f"- created_this_run: {created.get('delivery_partners', 0)}")
        print(f"- total_partners: {len(partners)}")
        for partner in partners[:5]:
            print(f"  - {partner.id}: {partner.name} | vehicle={partner.vehicle_type} | rating={float(partner.rating or 0):.1f}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
