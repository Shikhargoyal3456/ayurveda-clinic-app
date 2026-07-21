from __future__ import annotations

import sqlite3

DB_PATH = "ayurveda.db"


def update_schema() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(doctor_activity_log)")
    columns = [col[1] for col in cursor.fetchall()]
    if "metadata" in columns and "extra_data" not in columns:
        cursor.execute("ALTER TABLE doctor_activity_log RENAME COLUMN metadata TO extra_data")
        print("✅ Renamed 'metadata' to 'extra_data'")
    conn.commit()
    conn.close()
    print("✅ Schema update complete!")


if __name__ == "__main__":
    update_schema()
