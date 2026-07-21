"""
Verify AI metrics schema
Run: python scripts/verify_schema.py
"""

from __future__ import annotations

import sqlite3


DB_PATH = "ayurveda.db"


def verify() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables = ["consultation_metrics", "ai_feedback", "doctor_activity_log"]
    for table in tables:
        print(f"\n📋 {table.upper()}:")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            not_null = "NOT NULL" if col[3] else ""
            default = f"DEFAULT {col[4]}" if col[4] is not None else ""
            print(f"  {col[1]} {col[2]} {not_null} {default}".strip())

        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  📊 Rows: {count}")

    conn.close()


if __name__ == "__main__":
    verify()
