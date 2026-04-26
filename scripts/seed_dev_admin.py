from __future__ import annotations

from app.config import settings
from app.database import SessionLocal
from app.models import Doctor


def main() -> None:
    if settings.is_production:
        raise SystemExit("Refusing to seed development admin privileges in production.")

    db = SessionLocal()
    try:
        doctor = db.get(Doctor, 1)
        if doctor is None:
            print("Doctor id=1 not found; nothing to seed.")
            return
        print(
            "Doctor id=1 is allowed to access admin routes in non-production "
            f"by routers.admin._require_admin. username={doctor.username!r}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
