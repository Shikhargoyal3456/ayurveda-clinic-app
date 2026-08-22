"""
Fixed migration for AI performance tracking
Handles all edge cases including NOT NULL constraints
Run: python scripts/migrate_ai_metrics_fixed.py
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta


DB_PATH = "ayurveda.db"
AI_METRICS_TABLES = {"consultation_metrics", "ai_feedback", "doctor_activity_log"}


def quote_identifier(identifier: str, allowed: set[str]) -> str:
    if identifier not in allowed:
        raise ValueError(f"Unexpected SQL identifier: {identifier}")
    return f'"{identifier}"'


def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> dict[str, tuple]:
    """Get list of column names for a table."""
    cursor.execute("SELECT * FROM pragma_table_info(?)", (table_name,))
    return {col[1]: col for col in cursor.fetchall()}


def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Check if a table exists."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def create_consultation_metrics(cursor: sqlite3.Cursor) -> None:
    """Create consultation_metrics table if missing."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS consultation_metrics (
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
    print("✅ consultation_metrics table ready")


def create_doctor_activity_log(cursor: sqlite3.Cursor) -> None:
    """Create doctor_activity_log table if missing."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS doctor_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            metadata TEXT,
            duration_seconds INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    print("✅ doctor_activity_log table ready")


def recreate_ai_feedback(cursor: sqlite3.Cursor) -> None:
    """Safely recreate ai_feedback table with correct schema."""
    print("🔧 Rebuilding ai_feedback table...")

    exists = table_exists(cursor, "ai_feedback")
    backup_name = "ai_feedback_backup"
    cursor.execute("DROP TABLE IF EXISTS ai_feedback_backup")

    if exists:
        columns = get_table_columns(cursor, "ai_feedback")
        has_not_null_rating = bool(columns.get("rating", (None, None, None, 0))[3])

        def expr(column_name: str, default_sql: str = "NULL") -> str:
            return column_name if column_name in columns else default_sql

        accepted_expr = expr("was_accepted", expr("accepted", "0"))
        modified_expr = expr("modified", "0")
        accuracy_expr = expr("accuracy_score", expr("rating", "0"))
        rating_expr = expr("rating", "0")
        created_expr = expr("created_at", "CURRENT_TIMESTAMP")
        feature_expr = expr("feature_type", "NULL")
        suggestion_expr = expr("ai_suggestion", "NULL")
        final_expr = expr("doctor_final", "NULL")
        feedback_text_expr = expr("feedback_text", "NULL")

        if has_not_null_rating:
            print("⚠️ rating column has NOT NULL constraint, handling gracefully...")

        cursor.execute(
            f"""
            CREATE TABLE ai_feedback_backup AS
            SELECT
                id,
                {expr("consultation_id", "NULL")} AS consultation_id,
                {expr("doctor_id", "0")} AS doctor_id,
                {feature_expr} AS feature_type,
                {suggestion_expr} AS ai_suggestion,
                {final_expr} AS doctor_final,
                COALESCE({accepted_expr}, 0) AS was_accepted,
                COALESCE({modified_expr}, 0) AS modified,
                COALESCE({accuracy_expr}, {rating_expr}, 0) AS accuracy_score,
                {feedback_text_expr} AS feedback_text,
                COALESCE({rating_expr}, 0) AS rating,
                COALESCE({created_expr}, CURRENT_TIMESTAMP) AS created_at
            FROM ai_feedback
            """
        )

        backup_count = cursor.execute("SELECT COUNT(*) FROM ai_feedback_backup").fetchone()[0]
        print(f"📦 Backed up {backup_count} rows from ai_feedback")
        cursor.execute("DROP TABLE ai_feedback")

    cursor.execute(
        """
        CREATE TABLE ai_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id INTEGER,
            doctor_id INTEGER NOT NULL,
            feature_type TEXT NOT NULL,
            ai_suggestion TEXT,
            doctor_final TEXT,
            was_accepted BOOLEAN DEFAULT 0,
            modified BOOLEAN DEFAULT 0,
            accuracy_score INTEGER DEFAULT 0,
            feedback_text TEXT,
            rating INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    print("✅ ai_feedback table created with correct schema")

    if exists:
        cursor.execute(
            """
            INSERT INTO ai_feedback (
                id, consultation_id, doctor_id, feature_type,
                ai_suggestion, doctor_final, was_accepted,
                modified, accuracy_score, feedback_text, rating, created_at
            )
            SELECT
                id, consultation_id, doctor_id, feature_type,
                ai_suggestion, doctor_final, was_accepted,
                modified, accuracy_score, feedback_text, rating, created_at
            FROM ai_feedback_backup
            """
        )
        restored_count = cursor.rowcount
        print(f"✅ Restored {restored_count} rows")
        cursor.execute("DROP TABLE ai_feedback_backup")


def seed_sample_data(cursor: sqlite3.Cursor) -> None:
    """Seed sample AI performance data for testing."""
    cursor.execute("SELECT COUNT(*) FROM consultation_metrics")
    if (cursor.fetchone()[0] or 0) > 0:
        print("⏭️ consultation_metrics already has rows, skipping seed")
        return

    cursor.execute("SELECT COUNT(*) FROM patients")
    if (cursor.fetchone()[0] or 0) == 0:
        print("⚠️ No patients found, skipping sample data")
        return

    doctor_id = 1
    try:
        cursor.execute("SELECT id FROM doctors LIMIT 1")
        row = cursor.fetchone()
        if row:
            doctor_id = row[0]
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT id FROM patients LIMIT 10")
    patient_ids = [row[0] for row in cursor.fetchall()]
    if not patient_ids:
        print("⚠️ No patients found, skipping sample data")
        return

    now = datetime.now()
    for i in range(1, 21):
        patient_id = random.choice(patient_ids)
        start_time = now - timedelta(days=random.randint(0, 30), hours=random.randint(8, 16))
        duration = random.randint(180, 600)
        end_time = start_time + timedelta(seconds=duration)
        ai_used = random.choice([0, 1, 1, 1])
        voice_duration = random.randint(30, 180) if ai_used else 0
        time_saved = random.randint(60, 240) if ai_used else 0

        cursor.execute(
            """
            INSERT INTO consultation_metrics (
                consultation_id, doctor_id, patient_id, start_time, end_time,
                duration_seconds, ai_used, ai_voice_enabled, ai_diagnosis_enabled,
                ai_prescription_enabled, voice_duration_seconds, manual_time_saved_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                i,
                doctor_id,
                patient_id,
                start_time.isoformat(),
                end_time.isoformat(),
                duration,
                ai_used,
                1 if ai_used and random.choice([0, 1]) else 0,
                1 if ai_used and random.choice([0, 1]) else 0,
                1 if ai_used and random.choice([0, 1]) else 0,
                voice_duration,
                time_saved,
            ),
        )

    cursor.execute("SELECT COUNT(*) FROM ai_feedback")
    if (cursor.fetchone()[0] or 0) == 0:
        features = ["diagnosis", "prescription", "voice", "vision"]
        medicines = ["Triphala Churna", "Dashmool Kadha", "Chitrakadi Vati", "Sanshamani Vati", "Ashwagandha"]
        diagnoses = ["Vata Imbalance", "Pitta Imbalance", "Kapha Imbalance", "Mixed Imbalance"]

        for i in range(1, 31):
            consultation_id = random.randint(1, 20)
            feature = random.choice(features)
            accepted = random.choice([0, 1, 1, 1, 1])
            modified = 1 if accepted and random.choice([0, 0, 1]) else 0
            accuracy = random.randint(3, 5) if accepted else random.randint(1, 3)
            suggestion = random.choice(medicines) if feature == "prescription" else random.choice(diagnoses)

            cursor.execute(
                """
                INSERT INTO ai_feedback (
                    consultation_id, doctor_id, feature_type,
                    ai_suggestion, doctor_final, was_accepted,
                    modified, accuracy_score, feedback_text, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    consultation_id,
                    doctor_id,
                    feature,
                    suggestion,
                    suggestion if accepted else f"Modified: {suggestion}",
                    accepted,
                    modified,
                    accuracy,
                    f"Sample feedback {i}",
                    accuracy,
                ),
            )

    cursor.execute("SELECT COUNT(*) FROM doctor_activity_log")
    if (cursor.fetchone()[0] or 0) == 0:
        for _ in range(24):
            cursor.execute(
                """
                INSERT INTO doctor_activity_log (
                    doctor_id, activity_type, duration_seconds, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    doctor_id,
                    random.choice(["consultation_start", "consultation_end", "ai_interaction"]),
                    random.randint(30, 600),
                    (now - timedelta(days=random.randint(0, 30))).isoformat(),
                ),
            )


def migrate() -> None:
    """Main migration function."""
    print("🔧 Running AI performance tracking migration...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        create_consultation_metrics(cursor)
        create_doctor_activity_log(cursor)
        recreate_ai_feedback(cursor)
        seed_sample_data(cursor)
        conn.commit()
        print("✅ Migration completed successfully!")

        for table in ["consultation_metrics", "ai_feedback", "doctor_activity_log"]:
            table_sql = quote_identifier(table, AI_METRICS_TABLES)
            cursor.execute(f"SELECT COUNT(*) FROM {table_sql}")
            print(f"📊 {table}: {cursor.fetchone()[0]} rows")
    except Exception as exc:
        conn.rollback()
        print(f"❌ Error during migration: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
