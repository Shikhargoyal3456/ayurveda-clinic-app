from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool


# DEPLOY-FULL-1: Ensure app imports work when Alembic runs from repo root or deploy containers.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import normalize_database_url  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import Appointment, CaseSheet, Doctor, Patient  # noqa: F401,E402
from models.care_plan import PatientCarePlan  # noqa: F401,E402
from models.medicine import Medicine, MedicineOrder, Pharmacy  # noqa: F401,E402
from models.outcome import Outcome  # noqa: F401,E402
from models.payment import Payment  # noqa: F401,E402
from models.prescription import Prescription  # noqa: F401,E402
from models.subscription import ClinicSubscription, SubscriptionUsage  # noqa: F401,E402
from models.supplier import Supplier  # noqa: F401,E402


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # DEPLOY-FULL-1: DATABASE_URL wins in production; alembic.ini provides a SQLite fallback for local checks.
    configured = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or "sqlite:///./ayurveda.db"
    return normalize_database_url(configured)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
