"""
Verify AI metrics schema
Run: python scripts/verify_schema.py
"""

from __future__ import annotations

import sqlite3


DB_PATH = "ayurveda.db"
TABLES = {"consultation_metrics", "ai_feedback", "doctor_activity_log"}


def quote_identifier(identifier: str) -> str:
    if identifier not in TABLES:
        raise ValueError(f"Unexpected SQL identifier: {identifier}")
    return f'"{identifier}"'


def verify() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for table in sorted(TABLES):
        print(f"\n📋 {table.upper()}:")
        cursor.execute("SELECT * FROM pragma_table_info(?)", (table,))
        columns = cursor.fetchall()
        for col in columns:
            not_null = "NOT NULL" if col[3] else ""
            default = f"DEFAULT {col[4]}" if col[4] is not None else ""
            print(f"  {col[1]} {col[2]} {not_null} {default}".strip())

        table_sql = quote_identifier(table)
        cursor.execute(f"SELECT COUNT(*) FROM {table_sql}")
        count = cursor.fetchone()[0]
        print(f"  📊 Rows: {count}")

    conn.close()


if __name__ == "__main__":
    verify()
