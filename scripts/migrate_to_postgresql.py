"""
Migrate SQLite to PostgreSQL
Run: python scripts/migrate_to_postgresql.py
"""
from __future__ import annotations

import os
import sqlite3

import psycopg2


def get_postgres_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432"),
        database=os.getenv("PG_DATABASE", "kash_ai"),
        user=os.getenv("PG_USER", "kash_user"),
        password=os.getenv("PG_PASSWORD", ""),
    )


def migrate():
    print("MIGRATING SQLITE TO POSTGRESQL...")
    sqlite_conn = sqlite3.connect("ayurveda.db")
    sqlite_cursor = sqlite_conn.cursor()
    pg_conn = get_postgres_connection()
    pg_cursor = pg_conn.cursor()
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in sqlite_cursor.fetchall()]
    for table in tables:
        if table.startswith("sqlite_"):
            continue
        print(f"Migrating table: {table}")
        sqlite_cursor.execute(f"PRAGMA table_info({table})")
        columns = sqlite_cursor.fetchall()
        col_names = [col[1] for col in columns]
        col_types = [col[2] for col in columns]
        column_defs = []
        for name, typ in zip(col_names, col_types):
            if typ == "INTEGER":
                pg_type = "INTEGER"
            elif typ == "REAL":
                pg_type = "FLOAT"
            elif typ == "DATETIME":
                pg_type = "TIMESTAMP"
            else:
                pg_type = "TEXT"
            column_defs.append(f"{name} {pg_type}")
        pg_cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(column_defs)})")
        sqlite_cursor.execute(f"SELECT * FROM {table}")
        rows = sqlite_cursor.fetchall()
        for row in rows:
            placeholders = ",".join(["%s"] * len(col_names))
            pg_cursor.execute(
                f"INSERT INTO {table} ({','.join(col_names)}) VALUES ({placeholders})",
                row,
            )
        print(f"  Migrated {len(rows)} rows")
    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()
    print("Migration complete")


if __name__ == "__main__":
    migrate()
