from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AIConversationHistory(Base):
    __tablename__ = "ai_conversation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True, default="")
    message: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    intent: Mapped[str] = mapped_column(String(50), default="general", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AIPrescriptionScan(Base):
    __tablename__ = "ai_prescriptions_scanned"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    image_url: Mapped[str] = mapped_column(String(500), default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    medicines: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="patient_upload", index=True)
    file_type: Mapped[str] = mapped_column(String(20), default="image")
    title: Mapped[str] = mapped_column(String(255), default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    verified_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    doctor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class MedicineInfoCache(Base):
    __tablename__ = "medicine_info_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medicine_name: Mapped[str] = mapped_column(String(255), index=True, default="")
    uses: Mapped[str] = mapped_column(Text, default="")
    side_effects: Mapped[str] = mapped_column(Text, default="")
    alternatives: Mapped[str] = mapped_column(Text, default="")
    precautions: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, index=True)


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    prediction_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
