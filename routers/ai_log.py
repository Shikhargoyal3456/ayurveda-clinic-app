from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class AILog(Base):
    __tablename__ = "ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)
    feature = Column(String(100), nullable=False, index=True)
    input_payload = Column(Text, nullable=False)
    raw_output = Column(Text, nullable=True)
    provider = Column(String(50), nullable=True)
    feedback_status = Column(String(50), default="pending", nullable=False)  # pending, accepted, rejected
    feedback_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=datetime.utcnow,
        nullable=False,
    )