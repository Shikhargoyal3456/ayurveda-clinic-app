"""
Migrate SQLite to PostgreSQL
Run: python scripts/migrate_to_postgresql.py
"""
from __future__ import annotations

import os
import re
import sqlite3

import psycopg2
from psycopg2 import sql


SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_sqlite_identifier(identifier: str) -> str:
    if not SQL_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unexpected SQL identifier: {identifier}")
    return f'"{identifier}"'


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
        sqlite_table = quote_sqlite_identifier(table)
        print(f"Migrating table: {table}")
        sqlite_cursor.execute("SELECT * FROM pragma_table_info(?)", (table,))
        columns = sqlite_cursor.fetchall()
        col_names = [col[1] for col in columns]
        col_types = [col[2] for col in columns]
        pg_types = []
        for name, typ in zip(col_names, col_types):
            quote_sqlite_identifier(name)
            if typ == "INTEGER":
                pg_type = "INTEGER"
            elif typ == "REAL":
                pg_type = "FLOAT"
            elif typ == "DATETIME":
                pg_type = "TIMESTAMP"
            else:
                pg_type = "TEXT"
            pg_types.append(pg_type)
        pg_cursor.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                sql.Identifier(table),
                sql.SQL(", ").join(
                    sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(pg_type))
                    for name, pg_type in zip(col_names, pg_types)
                ),
            )
        )
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table}")
        rows = sqlite_cursor.fetchall()
        for row in rows:
            pg_cursor.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(sql.Identifier(name) for name in col_names),
                    sql.SQL(", ").join(sql.Placeholder() for _ in col_names),
                ),
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
