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
from models.marketplace import PharmacyStore  # noqa: E402
from services.marketplace_service import ensure_marketplace_seed_data  # noqa: E402


def main() -> int:
    init_db()
    created = ensure_marketplace_seed_data()

    db = SessionLocal()
    try:
        stores = db.query(PharmacyStore).order_by(PharmacyStore.rating.desc()).all()
        print("Pharmacy marketplace seed complete.")
        print(f"- created_this_run: {created.get('pharmacy_stores', 0)}")
        print(f"- total_stores: {len(stores)}")
        for store in stores[:5]:
            print(f"  - {store.id}: {store.store_name} | rating={float(store.rating or 0):.1f}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
