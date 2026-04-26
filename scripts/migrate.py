#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_alembic() -> bool:
    # DEPLOY-FULL-1: Prefer real Alembic in production images; local runtimes can fall back safely.
    try:
        from alembic import command
        from alembic.config import Config
    except Exception as exc:
        print(f"Alembic unavailable, using init_db fallback: {exc}")
        return False

    config_path = ROOT / "alembic.ini"
    if not config_path.exists():
        print("alembic.ini missing, using init_db fallback")
        return False

    cfg = Config(str(config_path))
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    return True


def _run_init_db_fallback() -> None:
    # DEPLOY-FULL-1: Preserve the repo's existing create_all + seed behavior for local/dev runtimes.
    from app.database import init_db

    init_db()


def main() -> int:
    migrated_with_alembic = _run_alembic()
    if not migrated_with_alembic:
        _run_init_db_fallback()
    print("Migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
