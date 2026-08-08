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

from app.database import Base, engine  # noqa: E402
from app.models import DietaryRecommendation, HerbalFormula, SamhitaAnalysis  # noqa: E402,F401


SAMHITA_TABLES = [
    "samhita_analyses",
    "dietary_recommendations",
    "herbal_formulas",
]


def main() -> int:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            SamhitaAnalysis.__table__,
            DietaryRecommendation.__table__,
            HerbalFormula.__table__,
        ],
    )
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    print("Samhita table check complete.")
    for name in SAMHITA_TABLES:
        print(f"- {name}: {'ready' if name in existing else 'missing'}")
    return 0 if all(name in existing for name in SAMHITA_TABLES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
