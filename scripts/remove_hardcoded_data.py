from __future__ import annotations

import sqlite3
from pathlib import Path


def remove_hardcoded_tables(database_path: str = "ayurveda.db") -> None:
    db_file = Path(database_path)
    if not db_file.exists():
        print(f"Database not found at {db_file.resolve()}. Nothing to remove.")
        return

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    tables_to_drop = [
        "medicines_master",
        "medicine_info_cache",
        "static_prescriptions",
        "disease_symptom_map",
    ]

    for table in tables_to_drop:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Removed table: {table}")
        except Exception as exc:
            print(f"Skipped table {table}: {exc}")

    conn.commit()
    conn.close()
    print("✅ Hardcoded data removed. Kash AI is now PURE AI!")


if __name__ == "__main__":
    remove_hardcoded_tables()
