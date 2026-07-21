from __future__ import annotations

import datetime as dt
import os
import sqlite3
from pathlib import Path


def _candidate_db_paths() -> list[Path]:
    cwd = Path.cwd()
    return [
        cwd / "ayurveda.db",
        cwd / "ayurveda_clinic.db",
    ]


def _resolve_db_path() -> Path:
    env_path = os.getenv("DATABASE_URL", "").strip()
    if env_path.startswith("sqlite:///"):
        raw = env_path.removeprefix("sqlite:///").split("?", 1)[0]
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate

    for candidate in _candidate_db_paths():
        if candidate.exists():
            return candidate
    return _candidate_db_paths()[0]


class DatabaseHelper:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _resolve_db_path()
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def connect(self) -> "DatabaseHelper":
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        return self

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def _table_columns(self, table: str) -> set[str]:
        assert self.cursor is not None
        rows = self.cursor.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def get_doctor(self) -> int:
        assert self.cursor is not None and self.conn is not None
        doctor_row = self.cursor.execute("SELECT id FROM doctors ORDER BY id ASC LIMIT 1").fetchone()
        if doctor_row:
            return int(doctor_row["id"])

        columns = self._table_columns("doctors")
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        if {"username", "password_hash", "full_name", "specialty"}.issubset(columns):
            self.cursor.execute(
                """
                INSERT INTO doctors (username, full_name, specialty, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("admin@kash.ai", "Dr. Kash AI", "ayurveda", "local-helper-placeholder", now),
            )
        elif {"name", "email", "phone"}.issubset(columns):
            self.cursor.execute(
                """
                INSERT INTO doctors (name, email, phone, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Dr. Kash AI", "admin@kash.ai", "8888888888", now),
            )
        else:
            raise RuntimeError("Unsupported doctors table schema.")
        self.conn.commit()
        return int(self.cursor.lastrowid)

    def add_patient(self, name: str, age: int, gender: str, phone: str, email: str | None = None, address: str | None = None) -> int:
        assert self.cursor is not None and self.conn is not None
        doctor_id = self.get_doctor()
        columns = self._table_columns("patients")
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        payload: dict[str, object] = {"doctor_id": doctor_id}
        if "name" in columns:
            payload["name"] = name
        if "age" in columns:
            payload["age"] = int(age)
        if "gender" in columns:
            payload["gender"] = gender
        if "phone" in columns:
            payload["phone"] = phone
        if "email" in columns and email is not None:
            payload["email"] = email
        if "address" in columns and address is not None:
            payload["address"] = address
        if "created_at" in columns:
            payload["created_at"] = now
        if "updated_at" in columns:
            payload["updated_at"] = now
        if "date_of_birth" in columns:
            payload["date_of_birth"] = None

        required = {"doctor_id", "name"}
        missing = sorted(required - payload.keys())
        if missing:
            raise RuntimeError(f"Missing required patient fields: {missing}")

        fields = ", ".join(payload.keys())
        placeholders = ", ".join(["?"] * len(payload))
        self.cursor.execute(
            f"INSERT INTO patients ({fields}) VALUES ({placeholders})",
            list(payload.values()),
        )
        self.conn.commit()
        return int(self.cursor.lastrowid)

    def get_all_patients(self):
        assert self.cursor is not None
        return self.cursor.execute(
            "SELECT id, name, age, gender, phone, email, doctor_id FROM patients ORDER BY id DESC"
        ).fetchall()

    def get_all_tables(self):
        assert self.cursor is not None
        rows = self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        ).fetchall()
        return [row["name"] for row in rows]


def add_test_patient():
    db = DatabaseHelper().connect()
    try:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        patient_id = db.add_patient(
            name=f"Test Patient {stamp}",
            age=30,
            gender="Male",
            phone=f"99999{stamp[-5:]}",
            email=f"test{stamp}@patient.com",
            address="Test Address",
        )
        print(f"Patient added with ID: {patient_id}")
        return patient_id
    finally:
        db.close()


def list_patients():
    db = DatabaseHelper().connect()
    try:
        patients = db.get_all_patients()
        for patient in patients:
            print(
                f"ID: {patient['id']}, Name: {patient['name']}, Age: {patient['age']}, "
                f"Gender: {patient['gender']}, Phone: {patient['phone']}"
            )
        return patients
    finally:
        db.close()


def show_tables():
    db = DatabaseHelper().connect()
    try:
        tables = db.get_all_tables()
        print("Tables and views in database:")
        for table in tables:
            print(f"  - {table}")
        return tables
    finally:
        db.close()


def show_database_info():
    db_path = _resolve_db_path()
    print(f"Database path: {db_path.resolve()}")
    print(f"File exists: {db_path.exists()}")
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"File size: {size} bytes ({size / 1024:.2f} KB)")
    print(f"SQLite module version: {sqlite3.sqlite_version}")


if __name__ == "__main__":
    print("=== KASH AI DATABASE HELPER ===")
    print("1. Show all tables")
    print("2. Add test patient")
    print("3. List all patients")
    print("4. Show database info")
    try:
        choice = input("Enter choice (1-4): ").strip()
    except EOFError:
        choice = "4"

    if choice == "1":
        show_tables()
    elif choice == "2":
        add_test_patient()
    elif choice == "3":
        list_patients()
    elif choice == "4":
        show_database_info()
    else:
        print("Unknown choice.")
