from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


logger = logging.getLogger(__name__)
SCHEMA_VERSION = 2


def _create_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    return create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def commit_with_retry(db, retries: int = 3, delay_seconds: float = 0.25) -> None:
    for attempt in range(retries):
        try:
            db.commit()
            return
        except OperationalError as exc:
            message = str(exc).lower()
            is_sqlite_lock = settings.database_url.startswith("sqlite") and "database is locked" in message
            if not is_sqlite_lock or attempt == retries - 1:
                db.rollback()
                raise
            db.rollback()
            logger.warning("SQLite database lock detected during commit. Retrying attempt %s/%s.", attempt + 1, retries)
            time.sleep(delay_seconds * (attempt + 1))


def current_schema_version() -> int:
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS app_metadata ("
                    "key TEXT PRIMARY KEY, "
                    "value TEXT NOT NULL)"
                )
            )
            value = connection.execute(
                text("SELECT value FROM app_metadata WHERE key = 'schema_version'")
            ).scalar_one_or_none()
            return int(value) if value is not None else 0
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not read schema version: %s", exc)
        return 0


def set_schema_version(version: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO app_metadata(key, value) VALUES ('schema_version', :value) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            ),
            {"value": str(version)},
        )


def ensure_schema_compatibility() -> dict[str, object]:
    version_before = current_schema_version()
    logger.info("Detected schema version %s", version_before)
    migration_summary = {
        "schema_version_before": version_before,
        "schema_version_after": version_before,
        "migrated": False,
        "message": "Schema already compatible.",
    }

    if version_before >= SCHEMA_VERSION:
        return migration_summary

    try:
        from scripts.migrate_db import migrate_database

        report = migrate_database(target_version=SCHEMA_VERSION)
        set_schema_version(SCHEMA_VERSION)
        migration_summary.update(
            {
                "schema_version_after": SCHEMA_VERSION,
                "migrated": bool(report.get("migrated")),
                "message": str(report.get("message", "Schema compatibility ensured.")),
                "details": report,
            }
        )
        logger.info("Schema migration report: %s", report)
    except Exception as exc:  # pragma: no cover
        logger.exception("Automatic schema compatibility check failed: %s", exc)
        migration_summary["message"] = f"Schema compatibility check failed: {exc}"
        migration_summary["error"] = str(exc)
    return migration_summary


def init_db() -> None:
    from app.models import Appointment, CaseSheet, Doctor, Patient  # noqa: F401
    from models.outcome import Outcome  # noqa: F401
    from models.payment import Payment  # noqa: F401
    from models.medicine import Medicine, MedicineOrder, Pharmacy  # noqa: F401
    from models.prescription import Prescription  # noqa: F401
    from models.subscription import ClinicSubscription, SubscriptionUsage  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_feature_schema()
    _enable_sqlite_wal_mode()
    compatibility = ensure_schema_compatibility()
    verify_schema()
    logger.info("Database ready. Schema compatibility: %s", compatibility)


def verify_schema() -> None:
    try:
        inspector = inspect(engine)
        unique_constraints = {constraint.get("name") for constraint in inspector.get_unique_constraints("patients")}
        missing = {"uq_patient_doctor_email", "uq_patient_doctor_name_dob"} - unique_constraints
        if missing:
            logger.warning(
                "Schema verification warning: missing constraints %s. Existing database detected without full hardening.",
                sorted(missing),
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Schema verification could not inspect database metadata: %s", exc)


def _enable_sqlite_wal_mode() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    try:
        with engine.connect() as connection:
            journal_mode = connection.execute(text("PRAGMA journal_mode=WAL;")).scalar()
        if str(journal_mode).lower() != "wal":
            logger.warning(
                "SQLite WAL mode could not be enabled. Existing database detected without full hardening. "
                "Consider migration."
            )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "SQLite WAL initialization failed. Existing database detected without full hardening. "
            "Consider migration. Error: %s",
            exc,
        )


def _ensure_feature_schema() -> None:
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        if "prescriptions" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("prescriptions")}
            if "follow_up_days" not in columns:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN follow_up_days INTEGER"))
        if "medicine_orders" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("medicine_orders")}
            if "paid_at" not in columns:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN paid_at DATETIME"))
            if "notification_failed" not in columns:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN notification_failed BOOLEAN DEFAULT 0"))
        if "clinic_subscriptions" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("clinic_subscriptions")}
            with engine.begin() as connection:
                if "user_id" not in columns:
                    connection.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN user_id INTEGER"))
                    if "doctor_id" in columns:
                        connection.execute(text("UPDATE clinic_subscriptions SET user_id = doctor_id WHERE user_id IS NULL"))
                if "plan_id" not in columns:
                    connection.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN plan_id VARCHAR(20) DEFAULT 'free'"))
                    if "plan" in columns:
                        connection.execute(text("UPDATE clinic_subscriptions SET plan_id = plan WHERE plan_id IS NULL OR plan_id = 'free'"))
                if "trial_end_date" not in columns:
                    connection.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN trial_end_date DATE"))
                if "razorpay_subscription_id" not in columns:
                    connection.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN razorpay_subscription_id VARCHAR(100)"))
                if "current_period_end" not in columns:
                    connection.execute(text("ALTER TABLE clinic_subscriptions ADD COLUMN current_period_end DATETIME"))
                    if "expires_at" in columns:
                        connection.execute(
                            text("UPDATE clinic_subscriptions SET current_period_end = expires_at WHERE current_period_end IS NULL")
                        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Feature schema compatibility check failed: %s", exc)
