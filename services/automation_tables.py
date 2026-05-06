from __future__ import annotations

from sqlalchemy import MetaData, Table, Column, DateTime, Float, Integer, String, Text, func

from app.database import engine


metadata = MetaData()


telemedicine_sessions_table = Table(
    "telemedicine_sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(100), unique=True, nullable=False, index=True),
    Column("patient_id", Integer, nullable=False, index=True),
    Column("doctor_id", Integer, nullable=False, index=True),
    Column("session_type", String(50), nullable=False, server_default="video"),
    Column("status", String(50), nullable=False, server_default="scheduled"),
    Column("start_time", DateTime, nullable=True),
    Column("end_time", DateTime, nullable=True),
    Column("ai_summary", Text, nullable=True),
    Column("prescription_id", Integer, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)


ai_processing_logs_table = Table(
    "ai_processing_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("entity_type", String(50), nullable=False, index=True),
    Column("entity_id", Integer, nullable=False, index=True),
    Column("action", String(100), nullable=False),
    Column("ai_decision", Text, nullable=True),
    Column("confidence", Float, nullable=True),
    Column("processed_at", DateTime, nullable=False, server_default=func.now()),
)


support_tickets_table = Table(
    "support_tickets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("query", Text, nullable=False),
    Column("ai_response", Text, nullable=True),
    Column("assigned_department", String(50), nullable=True),
    Column("status", String(50), nullable=False, server_default="open"),
    Column("resolved_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)


def ensure_automation_tables() -> None:
    metadata.create_all(bind=engine)
