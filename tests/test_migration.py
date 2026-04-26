from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal


def test_migration_runner_creates_and_seeds_suppliers():
    # DEPLOY-FULL-1: scripts/migrate.py must work with Alembic when available and init_db fallback locally.
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "scripts/migrate.py"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Migration complete" in result.stdout

    db = SessionLocal()
    try:
        suppliers = db.execute(text("SELECT id, name FROM suppliers ORDER BY id")).fetchall()
    finally:
        db.close()

    assert ("sup_1", "Pharma Distributor A") in suppliers
    assert ("sup_2", "Ayurveda Supplier B") in suppliers


def test_alembic_deploy_files_exist():
    # DEPLOY-FULL-1: Deployment environments have the standard Alembic entry files.
    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").exists()
    assert (root / "alembic" / "env.py").exists()
    assert (root / "alembic" / "versions" / "add_suppliers.py").exists()
