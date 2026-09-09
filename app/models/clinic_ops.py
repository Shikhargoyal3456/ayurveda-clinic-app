from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DoctorActionLog(Base):
    __tablename__ = "doctor_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(120), index=True)
    target_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class PrescriptionDeliveryLog(Base):
    __tablename__ = "prescription_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True, index=True)
    email_address: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class EmergencyAlertLog(Base):
    __tablename__ = "emergency_alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True, index=True)
    triggering_keyword: Mapped[str] = mapped_column(String(255), index=True)
    severity: Mapped[str] = mapped_column(String(40), default="emergency", index=True)
    full_text_context: Mapped[str] = mapped_column(Text, default="")
    action_taken: Mapped[str] = mapped_column(String(80), default="detected", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class PatientHealthPassport(Base):
    __tablename__ = "patient_health_passports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), unique=True, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True, index=True)
    prakriti: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    vikriti: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    visit_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    prescriptions: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    ongoing_medications: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    contraindications: Mapped[list[str]] = mapped_column(JSON, default=list)
    follow_up_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    lifestyle_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, index=True)
