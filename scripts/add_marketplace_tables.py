from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import inspect


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SESSION_HTTPS_ONLY", "false")
os.environ.setdefault("HTTPS_REDIRECT_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("APP_ENV", "testing")

from app.database import engine, init_db  # noqa: E402


MARKETPLACE_TABLES = [
    "pharmacy_stores",
    "lab_stores",
    "delivery_partners",
    "order_deliveries",
]


def main() -> int:
    init_db()
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    created = [name for name in MARKETPLACE_TABLES if name in existing]

    print("Marketplace table check complete.")
    for name in MARKETPLACE_TABLES:
        status = "ready" if name in created else "missing"
        print(f"- {name}: {status}")

    return 0 if len(created) == len(MARKETPLACE_TABLES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
