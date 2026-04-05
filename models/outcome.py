from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("case_sheets.id"), index=True, nullable=True)
    improvement_status: Mapped[str] = mapped_column(String(20), index=True)
    symptom_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[date] = mapped_column(Date, index=True)

    patient = relationship("Patient")
    case = relationship("CaseSheet")

