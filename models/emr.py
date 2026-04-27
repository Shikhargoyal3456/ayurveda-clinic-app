from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EMRPatientProfile(Base):
    __tablename__ = "emr_patient_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), unique=True, index=True)
    ur_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    profile_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    medical_history: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    ayurveda_profile: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    allergies: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    family_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    emergency_contact: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    consent_flags: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    patient = relationship("Patient")


class EMRConsultation(Base):
    __tablename__ = "emr_consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True, index=True)
    system_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    title: Mapped[str] = mapped_column(String(255), default="Consultation")
    chief_complaint: Mapped[str] = mapped_column(Text, default="")
    history_of_present_illness: Mapped[str] = mapped_column(Text, default="")
    notes_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    diagnosis_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    treatment_plan: Mapped[str] = mapped_column(Text, default="")
    followup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMRPrescription(Base):
    __tablename__ = "emr_prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("emr_consultations.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    system_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    items_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    refill_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMRVital(Base):
    __tablename__ = "emr_vitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("emr_consultations.id"), nullable=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMRLabOrder(Base):
    __tablename__ = "emr_lab_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("emr_consultations.id"), nullable=True, index=True)
    lab_name: Mapped[str] = mapped_column(String(255), default="Integrated Diagnostics")
    priority: Mapped[str] = mapped_column(String(32), default="routine")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    tests_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    results_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMRAssessment(Base):
    __tablename__ = "emr_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("emr_consultations.id"), nullable=True, index=True)
    assessment_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMROutcome(Base):
    __tablename__ = "emr_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("emr_consultations.id"), nullable=True, index=True)
    outcome_type: Mapped[str] = mapped_column(String(64), index=True)
    parameter_name: Mapped[str] = mapped_column(String(255))
    baseline_value: Mapped[str] = mapped_column(String(100), default="")
    current_value: Mapped[str] = mapped_column(String(100), default="")
    improvement_percentage: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    patient = relationship("Patient")


class EMRConsentForm(Base):
    __tablename__ = "emr_consent_forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(40), default="v1.0")
    status: Mapped[str] = mapped_column(String(32), default="signed")
    signature_name: Mapped[str] = mapped_column(String(160), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    audit_trail: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")


class EMRAuditLog(Base):
    __tablename__ = "emr_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(255), index=True)
    record_type: Mapped[str] = mapped_column(String(100), default="generic")
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    user = relationship("Doctor")
    patient = relationship("Patient")
