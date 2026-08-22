"""
Fix local SQLite schema drift for Kash AI.

Run from the project root:
    python scripts/fix_schema.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "ayurveda.db"
ALLOWED_TABLES = {"ai_feedback", "consultation_metrics"}
ALLOWED_COLUMN_TYPES = {
    "INTEGER",
    "TEXT",
    "BOOLEAN DEFAULT 0",
    "DATETIME",
    "DATETIME DEFAULT CURRENT_TIMESTAMP",
}


def quote_identifier(identifier: str, allowed: set[str]) -> str:
    if identifier not in allowed:
        raise ValueError(f"Unexpected SQL identifier: {identifier}")
    return f'"{identifier}"'


def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute("SELECT name FROM pragma_table_info(?)", (table_name,))
    return {str(row[0]) for row in cursor.fetchall()}


def ensure_columns(cursor: sqlite3.Cursor, table_name: str, columns: dict[str, str]) -> int:
    existing = table_columns(cursor, table_name)
    print(f"Columns in {table_name}: {sorted(existing)}")

    added = 0
    table_sql = quote_identifier(table_name, ALLOWED_TABLES)
    for column_name, column_type in columns.items():
        if column_name in existing:
            continue
        if column_type not in ALLOWED_COLUMN_TYPES:
            raise ValueError(f"Unexpected SQL column type for {column_name}: {column_type}")
        column_sql = quote_identifier(column_name, set(columns))
        cursor.execute(f"ALTER TABLE {table_sql} ADD COLUMN {column_sql} {column_type}")
        print(f"Added {table_name}.{column_name} ({column_type})")
        added += 1
    return added


def fix_ai_feedback(cursor: sqlite3.Cursor) -> int:
    if not table_exists(cursor, "ai_feedback"):
        cursor.execute(
            """
            CREATE TABLE ai_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consultation_id INTEGER,
                prescription_id INTEGER,
                case_id INTEGER,
                patient_id INTEGER,
                doctor_id INTEGER,
                field_name TEXT,
                feature_type TEXT,
                ai_suggestion TEXT,
                doctor_correction TEXT,
                doctor_final TEXT,
                rating INTEGER,
                accuracy_score INTEGER,
                accepted BOOLEAN DEFAULT 0,
                was_accepted BOOLEAN DEFAULT 0,
                modified BOOLEAN DEFAULT 0,
                notes TEXT,
                feedback_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        print("Created ai_feedback table")
        return 0

    return ensure_columns(
        cursor,
        "ai_feedback",
        {
            "consultation_id": "INTEGER",
            "prescription_id": "INTEGER",
            "case_id": "INTEGER",
            "patient_id": "INTEGER",
            "doctor_id": "INTEGER",
            "field_name": "TEXT",
            "feature_type": "TEXT",
            "ai_suggestion": "TEXT",
            "doctor_correction": "TEXT",
            "doctor_final": "TEXT",
            "rating": "INTEGER",
            "accuracy_score": "INTEGER",
            "accepted": "BOOLEAN DEFAULT 0",
            "was_accepted": "BOOLEAN DEFAULT 0",
            "modified": "BOOLEAN DEFAULT 0",
            "notes": "TEXT",
            "feedback_text": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
    )


def fix_consultation_metrics(cursor: sqlite3.Cursor) -> int:
    if not table_exists(cursor, "consultation_metrics"):
        cursor.execute(
            """
            CREATE TABLE consultation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consultation_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration_seconds INTEGER,
                ai_used BOOLEAN DEFAULT 0,
                ai_voice_enabled BOOLEAN DEFAULT 0,
                ai_vision_enabled BOOLEAN DEFAULT 0,
                ai_prescription_enabled BOOLEAN DEFAULT 0,
                ai_diagnosis_enabled BOOLEAN DEFAULT 0,
                voice_duration_seconds INTEGER,
                manual_time_saved_seconds INTEGER,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        print("Created consultation_metrics table")
        return 0

    return ensure_columns(
        cursor,
        "consultation_metrics",
        {
            "consultation_id": "INTEGER",
            "doctor_id": "INTEGER",
            "patient_id": "INTEGER",
            "start_time": "DATETIME",
            "end_time": "DATETIME",
            "duration_seconds": "INTEGER",
            "ai_used": "BOOLEAN DEFAULT 0",
            "ai_voice_enabled": "BOOLEAN DEFAULT 0",
            "ai_vision_enabled": "BOOLEAN DEFAULT 0",
            "ai_prescription_enabled": "BOOLEAN DEFAULT 0",
            "ai_diagnosis_enabled": "BOOLEAN DEFAULT 0",
            "voice_duration_seconds": "INTEGER",
            "manual_time_saved_seconds": "INTEGER",
            "notes": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        },
    )


def print_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    print("Tables in database:")
    for (table_name,) in cursor.fetchall():
        print(f"  - {table_name}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    print(f"Fixing database schema: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        added = fix_ai_feedback(cursor)
        added += fix_consultation_metrics(cursor)
        conn.commit()
        print_tables(cursor)

    if added:
        print(f"Schema fix complete. Added {added} column(s).")
    else:
        print("Schema already up to date.")


if __name__ == "__main__":
    main()
