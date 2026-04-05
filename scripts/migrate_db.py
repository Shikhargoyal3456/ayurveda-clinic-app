from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"
LOG_FILE = LOGS_DIR / "migration.log"


def configure_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("migration")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


LOGGER = configure_logging()


def resolve_database_path() -> Path:
    preferred = BASE_DIR / "ayurveda.db"
    current = BASE_DIR / "ayurveda_clinic.db"
    if preferred.exists():
        return preferred
    if current.exists():
        return current
    return preferred


def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def column_names(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    if not table_exists(cursor, table_name):
        return set()
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def trigger_exists(cursor: sqlite3.Cursor, trigger_name: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name = ?",
        (trigger_name,),
    ).fetchone()
    return row is not None


def create_backup(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"{db_path.stem}_migration_backup_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    LOGGER.info("Created migration backup at %s", backup_path)
    return backup_path


def collect_pending_changes(cursor: sqlite3.Cursor) -> list[str]:
    changes: list[str] = []
    if table_exists(cursor, "patients"):
        patient_columns = column_names(cursor, "patients")
        if "date_of_birth" not in patient_columns:
            changes.append("patients.date_of_birth column missing")
        if not index_exists(cursor, "uq_patients_active_name_dob"):
            changes.append("unique patient name/date_of_birth index missing")
        for index_name in ("idx_patients_name", "idx_patients_email", "idx_patients_phone"):
            if not index_exists(cursor, index_name):
                changes.append(f"{index_name} missing")
        for trigger_name in ("trg_patients_audit_insert", "trg_patients_audit_update", "trg_patients_audit_delete"):
            if not trigger_exists(cursor, trigger_name):
                changes.append(f"{trigger_name} missing")
    if table_exists(cursor, "appointments") and not index_exists(cursor, "idx_appointments_date_patient"):
        changes.append("appointments date/patient index missing")
    if table_exists(cursor, "cases") and not index_exists(cursor, "idx_cases_patient_status"):
        changes.append("cases patient/status index missing")
    if table_exists(cursor, "case_sheets") and not index_exists(cursor, "idx_case_sheets_patient_status"):
        changes.append("case_sheets patient/status index missing")
    if table_exists(cursor, "followups") and not index_exists(cursor, "idx_followups_case_date"):
        changes.append("followups case/date index missing")
    return changes


def ensure_patients(cursor: sqlite3.Cursor) -> list[str]:
    changes: list[str] = []
    if not table_exists(cursor, "patients"):
        LOGGER.info("patients table does not exist yet; skipping patient migration")
        return changes

    patient_columns = column_names(cursor, "patients")
    if "date_of_birth" not in patient_columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN date_of_birth TEXT")
        changes.append("Added patients.date_of_birth column")

    if not table_exists(cursor, "patients_audit"):
        cursor.execute(
            """
            CREATE TABLE patients_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                action TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                patient_name TEXT,
                email TEXT,
                phone TEXT,
                payload TEXT
            )
            """
        )
        changes.append("Created patients_audit table")

    if not index_exists(cursor, "idx_patients_name"):
        cursor.execute("CREATE INDEX idx_patients_name ON patients(name)")
        changes.append("Created idx_patients_name")
    if "email" in column_names(cursor, "patients") and not index_exists(cursor, "idx_patients_email"):
        cursor.execute("CREATE INDEX idx_patients_email ON patients(email)")
        changes.append("Created idx_patients_email")
    if "phone" in column_names(cursor, "patients") and not index_exists(cursor, "idx_patients_phone"):
        cursor.execute("CREATE INDEX idx_patients_phone ON patients(phone)")
        changes.append("Created idx_patients_phone")

    patient_columns = column_names(cursor, "patients")
    if not index_exists(cursor, "uq_patients_active_name_dob"):
        if "is_active" in patient_columns:
            cursor.execute(
                """
                CREATE UNIQUE INDEX uq_patients_active_name_dob
                ON patients(name, date_of_birth)
                WHERE is_active = 1 AND date_of_birth IS NOT NULL
                """
            )
        else:
            cursor.execute(
                """
                CREATE UNIQUE INDEX uq_patients_active_name_dob
                ON patients(name, date_of_birth)
                WHERE date_of_birth IS NOT NULL
                """
            )
        changes.append("Created active patient unique index")

    trigger_sql = {
        "trg_patients_audit_insert": """
            CREATE TRIGGER trg_patients_audit_insert
            AFTER INSERT ON patients
            BEGIN
                INSERT INTO patients_audit(patient_id, action, patient_name, email, phone, payload)
                VALUES (NEW.id, 'insert', NEW.name, COALESCE(NEW.email, ''), COALESCE(NEW.phone, ''), json_object('name', NEW.name, 'email', COALESCE(NEW.email, ''), 'phone', COALESCE(NEW.phone, '')));
            END
        """,
        "trg_patients_audit_update": """
            CREATE TRIGGER trg_patients_audit_update
            AFTER UPDATE ON patients
            BEGIN
                INSERT INTO patients_audit(patient_id, action, patient_name, email, phone, payload)
                VALUES (NEW.id, 'update', NEW.name, COALESCE(NEW.email, ''), COALESCE(NEW.phone, ''), json_object('old_name', OLD.name, 'new_name', NEW.name, 'old_email', COALESCE(OLD.email, ''), 'new_email', COALESCE(NEW.email, '')));
            END
        """,
        "trg_patients_audit_delete": """
            CREATE TRIGGER trg_patients_audit_delete
            AFTER DELETE ON patients
            BEGIN
                INSERT INTO patients_audit(patient_id, action, patient_name, email, phone, payload)
                VALUES (OLD.id, 'delete', OLD.name, COALESCE(OLD.email, ''), COALESCE(OLD.phone, ''), json_object('name', OLD.name, 'email', COALESCE(OLD.email, ''), 'phone', COALESCE(OLD.phone, '')));
            END
        """,
    }
    for trigger_name, sql in trigger_sql.items():
        if not trigger_exists(cursor, trigger_name):
            cursor.execute(sql)
            changes.append(f"Created {trigger_name}")
    return changes


def ensure_indexes(cursor: sqlite3.Cursor) -> list[str]:
    changes: list[str] = []
    if table_exists(cursor, "appointments"):
        appointment_columns = column_names(cursor, "appointments")
        if "appointment_date" in appointment_columns and "patient_id" in appointment_columns:
            if not index_exists(cursor, "idx_appointments_date_patient"):
                cursor.execute("CREATE INDEX idx_appointments_date_patient ON appointments(appointment_date, patient_id)")
                changes.append("Created idx_appointments_date_patient on appointments(appointment_date, patient_id)")
        elif "date" in appointment_columns and "patient_id" in appointment_columns:
            if not index_exists(cursor, "idx_appointments_date_patient"):
                cursor.execute("CREATE INDEX idx_appointments_date_patient ON appointments(date, patient_id)")
                changes.append("Created idx_appointments_date_patient on appointments(date, patient_id)")

    if table_exists(cursor, "cases"):
        case_columns = column_names(cursor, "cases")
        if "patient_id" in case_columns and "status" in case_columns and not index_exists(cursor, "idx_cases_patient_status"):
            cursor.execute("CREATE INDEX idx_cases_patient_status ON cases(patient_id, status)")
            changes.append("Created idx_cases_patient_status")
    elif table_exists(cursor, "case_sheets"):
        case_columns = column_names(cursor, "case_sheets")
        if "patient_id" in case_columns:
            if "status" in case_columns:
                if not index_exists(cursor, "idx_case_sheets_patient_status"):
                    cursor.execute("CREATE INDEX idx_case_sheets_patient_status ON case_sheets(patient_id, status)")
                    changes.append("Created idx_case_sheets_patient_status")
            else:
                if not index_exists(cursor, "idx_case_sheets_patient_status"):
                    cursor.execute("CREATE INDEX idx_case_sheets_patient_status ON case_sheets(patient_id, created_at)")
                    changes.append("Created idx_case_sheets_patient_status fallback index")

    if table_exists(cursor, "followups"):
        followup_columns = column_names(cursor, "followups")
        if "case_id" in followup_columns and "followup_date" in followup_columns and not index_exists(cursor, "idx_followups_case_date"):
            cursor.execute("CREATE INDEX idx_followups_case_date ON followups(case_id, followup_date)")
            changes.append("Created idx_followups_case_date")
    return changes


def optimize_database(connection: sqlite3.Connection) -> list[str]:
    changes: list[str] = []
    connection.commit()
    connection.execute("ANALYZE")
    changes.append("Ran ANALYZE")
    connection.execute("VACUUM")
    changes.append("Ran VACUUM")
    return changes


def run_migration(check_only: bool = False) -> int:
    db_path = resolve_database_path()
    LOGGER.info("Using database path: %s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        pending = collect_pending_changes(cursor)
        if check_only:
            if pending:
                LOGGER.warning("Migration required: %s", "; ".join(pending))
                return 1
            LOGGER.info("Migration check complete. No changes needed.")
            return 0

    create_backup(db_path)
    all_changes: list[str] = []
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        all_changes.extend(ensure_patients(cursor))
        all_changes.extend(ensure_indexes(cursor))
        connection.commit()
        all_changes.extend(optimize_database(connection))

    if all_changes:
        for change in all_changes:
            LOGGER.info(change)
    else:
        LOGGER.info("No migration changes were required.")
    return 0


def migrate_database(target_version: int = None, connection=None):
    """
    Function called by app/database.py during startup
    This performs automatic migration without CLI arguments
    
    Args:
        target_version: Target schema version (ignored for SQLite, kept for compatibility)
        connection: Optional database connection (if None, creates new connection)
    """
    import logging
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    
    # Get database path
    db_path = resolve_database_path()
    
    # Log the target version (for debugging)
    if target_version:
        logger.info(f"Migration target version: {target_version}")
    
    # Check if database exists
    if not db_path.exists():
        logger.info("Database does not exist yet, skipping migration")
        return {"migrated": False, "changes": [], "schema_version": 0}
    
    # Check if migration is needed
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            pending = collect_pending_changes(cursor)
            
            if not pending:
                logger.info("No pending migrations needed")
                return {"migrated": False, "changes": [], "schema_version": 1}
    except Exception as e:
        logger.warning(f"Error checking migration status: {e}")
    
    # Create backup
    backup_path = create_backup(db_path)
    
    # Run migration
    all_changes = []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Run patient-related migrations
            patient_changes = ensure_patients(cursor)
            all_changes.extend(patient_changes)
            
            # Run index migrations
            index_changes = ensure_indexes(cursor)
            all_changes.extend(index_changes)
            
            conn.commit()
            
            # Optimize
            optimize_changes = optimize_database(conn)
            all_changes.extend(optimize_changes)
        
        result = {
            "migrated": len(all_changes) > 0,
            "changes": all_changes,
            "backup_path": str(backup_path) if backup_path else None,
            "schema_version": 1  # After migration, we're at version 1
        }
        
        logger.info(f"Migration completed with {len(all_changes)} changes")
        return result
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {
            "migrated": False,
            "error": str(e),
            "backup_path": str(backup_path) if backup_path else None,
            "schema_version": 0
        }


def check_migration_needed():
    """Check if migration is needed - called by database.py"""
    db_path = resolve_database_path()
    
    if not db_path.exists():
        return {"needed": False, "reason": "Database does not exist yet"}
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            pending = collect_pending_changes(cursor)
            
            return {
                "needed": len(pending) > 0,
                "pending_changes": pending,
                "count": len(pending)
            }
    except Exception as e:
        return {
            "needed": False,
            "error": str(e)
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite migration helper for Ayurveda Clinic Management System")
    parser.add_argument("--check-only", action="store_true", help="Only report whether migration is required")
    args = parser.parse_args()
    return run_migration(check_only=args.check_only)


if __name__ == "__main__":
    raise SystemExit(main())