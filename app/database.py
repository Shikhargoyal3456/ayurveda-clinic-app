from __future__ import annotations

import hashlib
import logging
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings


logger = logging.getLogger(__name__)
SCHEMA_VERSION = 2
SQLITE_FALLBACK_URL = "sqlite:///./ayurveda.db?cache=shared&timeout=30"


def _is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _engine_is_sqlite() -> bool:
    return engine.url.drivername.startswith("sqlite")


def _create_engine(database_url: str | None = None):
    database_url = database_url or settings.database_url
    connect_args = {}
    engine_kwargs = {
        "future": True,
        "pool_pre_ping": True,
        "poolclass": QueuePool,
        "pool_size": max(1, settings.db_pool_size or 10),
        "max_overflow": max(0, settings.db_max_overflow or 20),
        "pool_timeout": max(1, settings.db_pool_timeout_seconds),
        "pool_recycle": max(30, settings.db_pool_recycle_seconds),
    }
    if _is_sqlite_url(database_url):
        # PROD-FIX-6: SQLite concurrent safety for local/small-launch mode.
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


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
            is_sqlite_lock = _engine_is_sqlite() and "database is locked" in message
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


def _run_database_startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_feature_schema()
    _ensure_admin_seed_data()
    _ensure_portal_test_users()
    _ensure_patient_user_profiles()
    _ensure_supplier_seed_data()
    _ensure_medicine_seed_data()
    _enable_sqlite_wal_mode()
    compatibility = ensure_schema_compatibility()
    verify_schema()
    logger.info("Database ready. Schema compatibility: %s", compatibility)


def _activate_sqlite_fallback(exc: Exception) -> None:
    # PROD-FIX-6: If PostgreSQL is configured but unreachable, keep the app bootable with a warning.
    global engine
    logger.warning(
        "Primary database failed during startup: %s. Falling back to SQLite at %s.",
        exc,
        SQLITE_FALLBACK_URL,
    )
    logger.warning(
        "Migration notice: move production data to PostgreSQL with Alembic, for example: "
        "alembic revision --autogenerate -m \"production schema\" && alembic upgrade head."
    )
    engine.dispose()
    engine = _create_engine(SQLITE_FALLBACK_URL)
    SessionLocal.configure(bind=engine)


def init_db() -> None:
    from app.models import Appointment, CaseSheet, Doctor, Patient  # noqa: F401
    from models.ai_features import AIConversationHistory, AIPrediction, AIPrescriptionScan, MedicineInfoCache  # noqa: F401
    from models.emr import (  # noqa: F401
        EMRAssessment,
        EMRAuditLog,
        EMRConsentForm,
        EMRConsultation,
        EMRLabOrder,
        EMROutcome,
        EMRPatientProfile,
        EMRPrescription,
        EMRVital,
    )
    from models.outcome import Outcome  # noqa: F401
    from models.marketplace import DeliveryPartner, LabStore, OrderDelivery, PharmacyStore  # noqa: F401
    from models.payment import Payment  # noqa: F401
    from models.medicine import MasterMedicine, Medicine, MedicineOrder, MedicineRequest, Pharmacy, PharmacyInventory, StockAdjustment, StockAlert  # noqa: F401
    from models.prescription import AIFeedback, Prescription  # noqa: F401
    from models.subscription import ClinicSubscription, SubscriptionUsage  # noqa: F401
    from models.supplier import Supplier  # noqa: F401
    from models.user import DeliveryProfile, DoctorProfile, LabProfile, PatientProfile, PharmacyProfile, User, UserProfile  # noqa: F401

    try:
        _run_database_startup()
    except OperationalError as exc:
        if _engine_is_sqlite():
            raise
        _activate_sqlite_fallback(exc)
        _run_database_startup()


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
    if not _engine_is_sqlite():
        return

    try:
        with engine.connect() as connection:
            connection.execute(text("PRAGMA busy_timeout = 30000;"))
            journal_mode = connection.execute(text("PRAGMA journal_mode=WAL;")).scalar()
            connection.execute(text("PRAGMA synchronous=NORMAL;"))
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
            with engine.begin() as connection:
                if "follow_up_days" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN follow_up_days INTEGER"))
                if "profile_id" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN profile_id INTEGER"))
                if "profile_name" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN profile_name VARCHAR(100)"))
                if "ai_rating" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN ai_rating INTEGER"))
                if "ai_accepted" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN ai_accepted BOOLEAN"))
                if "ai_feedback" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN ai_feedback TEXT"))
                if "feedback_updated_at" not in columns:
                    connection.execute(text("ALTER TABLE prescriptions ADD COLUMN feedback_updated_at DATETIME"))
        if "ai_feedback" not in existing_tables:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS ai_feedback ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "prescription_id INTEGER, "
                        "case_id INTEGER, "
                        "doctor_id INTEGER NOT NULL, "
                        "rating INTEGER CHECK (rating >= 1 AND rating <= 5), "
                        "accepted BOOLEAN, "
                        "notes TEXT, "
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                        "FOREIGN KEY (prescription_id) REFERENCES prescriptions(id), "
                        "FOREIGN KEY (doctor_id) REFERENCES doctors(id))"
                    )
                )
        if "medicine_orders" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("medicine_orders")}
            with engine.begin() as connection:
                if "patient_user_id" not in columns:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN patient_user_id INTEGER"))
                if "profile_id" not in columns:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN profile_id INTEGER"))
                if "profile_name" not in columns:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN profile_name VARCHAR(100)"))
                if "paid_at" not in columns:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN paid_at DATETIME"))
                if "notification_failed" not in columns:
                    connection.execute(text("ALTER TABLE medicine_orders ADD COLUMN notification_failed BOOLEAN DEFAULT 0"))
        if "medicines" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("medicines")}
            with engine.begin() as connection:
                if "mrp" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN mrp INTEGER"))
                    connection.execute(text("UPDATE medicines SET mrp = price WHERE mrp IS NULL"))
                if "brand" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN brand VARCHAR(160)"))
                if "description" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN description TEXT"))
                if "image_url" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN image_url VARCHAR(255)"))
                if "stock" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN stock INTEGER DEFAULT 0"))
                    connection.execute(text("UPDATE medicines SET stock = 100 WHERE stock IS NULL OR stock = 0"))
                if "created_at" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN created_at DATETIME"))
                    connection.execute(text("UPDATE medicines SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
                if "expiry_date" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN expiry_date DATE"))
                if "barcode" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN barcode VARCHAR(64)"))
                if "master_medicine_id" not in columns:
                    connection.execute(text("ALTER TABLE medicines ADD COLUMN master_medicine_id INTEGER"))
        if "medicines_master" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("medicines_master")}
            with engine.begin() as connection:
                if "images_json" not in columns:
                    connection.execute(text("ALTER TABLE medicines_master ADD COLUMN images_json TEXT"))
                if "default_image_url" not in columns:
                    connection.execute(text("ALTER TABLE medicines_master ADD COLUMN default_image_url VARCHAR(500)"))
        if "stock_adjustments" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("stock_adjustments")}
            with engine.begin() as connection:
                if "adjusted_by" not in columns:
                    connection.execute(text("ALTER TABLE stock_adjustments ADD COLUMN adjusted_by INTEGER"))
                if "reason" not in columns:
                    connection.execute(text("ALTER TABLE stock_adjustments ADD COLUMN reason VARCHAR(255)"))
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
        if "pharmacy_inventory" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("pharmacy_inventory")}
            with engine.begin() as connection:
                if "is_clearance" not in columns:
                    connection.execute(text("ALTER TABLE pharmacy_inventory ADD COLUMN is_clearance BOOLEAN DEFAULT 0"))
                if "clearance_price" not in columns:
                    connection.execute(text("ALTER TABLE pharmacy_inventory ADD COLUMN clearance_price NUMERIC(10, 2)"))
                if "clearance_reason" not in columns:
                    connection.execute(text("ALTER TABLE pharmacy_inventory ADD COLUMN clearance_reason VARCHAR(255)"))
        if "ai_prescriptions_scanned" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("ai_prescriptions_scanned")}
            with engine.begin() as connection:
                if "status" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN status VARCHAR(30) DEFAULT 'pending'"))
                if "source_type" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN source_type VARCHAR(40) DEFAULT 'patient_upload'"))
                if "file_type" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN file_type VARCHAR(20) DEFAULT 'image'"))
                if "title" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN title VARCHAR(255) DEFAULT ''"))
                if "review_notes" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN review_notes TEXT DEFAULT ''"))
                if "verified_by_user_id" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN verified_by_user_id INTEGER"))
                if "doctor_user_id" not in columns:
                    connection.execute(text("ALTER TABLE ai_prescriptions_scanned ADD COLUMN doctor_user_id INTEGER"))
        if "doctor_profiles" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("doctor_profiles")}
            with engine.begin() as connection:
                if "doctor_type" not in columns:
                    connection.execute(text("ALTER TABLE doctor_profiles ADD COLUMN doctor_type VARCHAR(50)"))
    except Exception as exc:  # pragma: no cover
        logger.warning("Feature schema compatibility check failed: %s", exc)


def _ensure_supplier_seed_data() -> None:
    # DEPLOY-FULL-1 / SUPPLIER-FULL-1: Seed default suppliers after metadata creates the table, without overwriting admin edits.
    try:
        from services.supplier_service import seed_default_suppliers

        seed_default_suppliers()
    except Exception as exc:  # pragma: no cover
        logger.warning("Supplier seed data could not be ensured: %s", exc)


def _ensure_medicine_seed_data() -> None:
    # PURE-AI: Explicitly disable static medicine seeding at startup.
    logger.info("Pure AI mode active: static medicine seed data is disabled.")


def _ensure_admin_seed_data() -> None:
    # CTO-FIX-1: Keep env-configured admin usernames actually usable by syncing a known password locally.
    admin_usernames = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    bootstrap_password = settings.admin_bootstrap_password.strip()
    if not admin_usernames or not bootstrap_password:
        return

    try:
        from app.auth import hash_password
        from app.models import Doctor
        from models.user import User, UserRole

        session = SessionLocal()
        try:
            for username in admin_usernames:
                doctor = session.query(Doctor).filter(Doctor.username == username).first()
                if doctor is None:
                    doctor = Doctor(
                        username=username,
                        full_name=settings.admin_bootstrap_full_name,
                        specialty="ayurveda",
                        password_hash=hash_password(bootstrap_password),
                    )
                    session.add(doctor)
                else:
                    doctor.password_hash = hash_password(bootstrap_password)
                    if not (doctor.full_name or "").strip():
                        doctor.full_name = settings.admin_bootstrap_full_name

                # Keep an explicit portal admin account available for role-based
                # routing when the configured admin username is an email address.
                if "@" in username:
                    portal_user = session.query(User).filter(User.email == username).first()
                    if portal_user is None:
                        phone_seed = str(int(hashlib.sha256(username.encode("utf-8")).hexdigest(), 16) % 10_000_000_000).zfill(10)
                        while session.query(User).filter(User.phone == phone_seed).first() is not None:
                            phone_seed = str((int(phone_seed) + 1) % 10_000_000_000).zfill(10)
                        portal_user = User(
                            email=username,
                            phone=phone_seed,
                            password_hash=hash_password(bootstrap_password),
                            full_name=settings.admin_bootstrap_full_name,
                            role=UserRole.admin,
                            is_verified=True,
                            is_active=True,
                        )
                        session.add(portal_user)
                    else:
                        portal_user.password_hash = hash_password(bootstrap_password)
                        portal_user.full_name = portal_user.full_name or settings.admin_bootstrap_full_name
                        portal_user.role = UserRole.admin
                        portal_user.is_active = True
                        portal_user.is_verified = True
            commit_with_retry(session)
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("Admin bootstrap data could not be ensured: %s", exc)


def _ensure_portal_test_users() -> None:
    # Keep local/demo environments usable by seeding role-based portal users
    # only when the portal users table is still empty.
    try:
        from app.auth import hash_password
        from models.user import DeliveryProfile, LabProfile, PatientProfile, PharmacyProfile, User, UserProfile, UserRole, VehicleType

        session = SessionLocal()
        try:
            if session.query(User.id).first() is not None:
                return

            default_password_hash = hash_password("test123")
            seeded_users = {
                "patient": User(
                    email="patient@test.com",
                    phone="9999999991",
                    password_hash=default_password_hash,
                    full_name="Test Patient",
                    role=UserRole.patient,
                    is_verified=True,
                    is_active=True,
                ),
                "doctor": User(
                    email="doctor@test.com",
                    phone="9999999992",
                    password_hash=default_password_hash,
                    full_name="Test Doctor",
                    role=UserRole.doctor,
                    is_verified=True,
                    is_active=True,
                ),
                "pharmacy": User(
                    email="pharmacy@test.com",
                    phone="9999999993",
                    password_hash=default_password_hash,
                    full_name="Test Pharmacy",
                    role=UserRole.pharmacy_owner,
                    is_verified=True,
                    is_active=True,
                ),
                "lab": User(
                    email="lab@test.com",
                    phone="9999999994",
                    password_hash=default_password_hash,
                    full_name="Test Lab",
                    role=UserRole.lab_owner,
                    is_verified=True,
                    is_active=True,
                ),
                "delivery": User(
                    email="delivery@test.com",
                    phone="9999999995",
                    password_hash=default_password_hash,
                    full_name="Test Delivery Partner",
                    role=UserRole.delivery_partner,
                    is_verified=True,
                    is_active=True,
                ),
            }
            for user in seeded_users.values():
                session.add(user)
            session.flush()

            session.add(PatientProfile(user_id=seeded_users["patient"].id))
            session.add(
                UserProfile(
                    user_id=seeded_users["patient"].id,
                    profile_name="Myself",
                    profile_avatar="👤",
                    relationship="Self",
                    is_primary=True,
                    is_active=True,
                )
            )
            session.add(
                PharmacyProfile(
                    user_id=seeded_users["pharmacy"].id,
                    pharmacy_name="Test Pharmacy Store",
                    gst_number="GSTTEST9993",
                    license_number="LIC-TEST-9993",
                    address="Sector 14, Gurugram",
                    is_open=True,
                    delivery_radius_km=5,
                    minimum_order_amount=199,
                )
            )
            session.add(
                LabProfile(
                    user_id=seeded_users["lab"].id,
                    lab_name="Test Lab Diagnostics",
                    accreditation_number="LAB-TEST-9994",
                    address="DLF Phase 1, Gurugram",
                    is_home_collection_available=True,
                )
            )
            session.add(
                DeliveryProfile(
                    user_id=seeded_users["delivery"].id,
                    vehicle_type=VehicleType.bike,
                    vehicle_number="DL01TEST9995",
                    dl_number="DL-TEST-9995",
                    is_available=True,
                )
            )
            commit_with_retry(session)
            logger.info("Seeded default portal test users for patient, doctor, pharmacy, lab, and delivery roles.")
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("Portal test users could not be ensured: %s", exc)


def _ensure_patient_user_profiles() -> None:
    try:
        from models.user import PatientProfile, User, UserProfile, UserRole

        session = SessionLocal()
        try:
            patient_users = session.query(User).filter(User.role == UserRole.patient).all()
            for user in patient_users:
                existing_profiles = (
                    session.query(UserProfile)
                    .filter(UserProfile.user_id == user.id, UserProfile.is_active.is_(True))
                    .order_by(UserProfile.id.asc())
                    .all()
                )
                if existing_profiles:
                    if not any(profile.is_primary for profile in existing_profiles):
                        existing_profiles[0].is_primary = True
                    continue
                patient_profile = session.get(PatientProfile, user.id)
                session.add(
                    UserProfile(
                        user_id=user.id,
                        profile_name=(user.full_name or "Myself").strip() or "Myself",
                        profile_avatar="👤",
                        relationship="Self",
                        date_of_birth=patient_profile.date_of_birth if patient_profile else None,
                        gender=patient_profile.gender if patient_profile else None,
                        blood_group=patient_profile.blood_group if patient_profile else None,
                        medical_conditions=patient_profile.medical_conditions if patient_profile else None,
                        allergies=patient_profile.allergies if patient_profile else None,
                        is_primary=True,
                        is_active=True,
                    )
                )
            commit_with_retry(session)
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("Patient user profiles could not be ensured: %s", exc)
