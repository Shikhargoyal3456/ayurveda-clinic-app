from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    specialty: Mapped[str] = mapped_column(
        String(50), default="ayurveda", index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    patients: Mapped[list["Patient"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")
    patient_queries: Mapped[list["PatientQuery"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")
    pending_reviews: Mapped[list["PendingReview"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("doctor_id", "email", name="uq_patient_doctor_email"),
        UniqueConstraint("doctor_id", "name", "date_of_birth", name="uq_patient_doctor_name_dob"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(30))
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    doctor: Mapped["Doctor"] = relationship(back_populates="patients")
    cases: Mapped[list["CaseSheet"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    patient_queries: Mapped[list["PatientQuery"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    pending_reviews: Mapped[list["PendingReview"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    samhita_analyses: Mapped[list["SamhitaAnalysis"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class CaseSheet(Base):
    __tablename__ = "case_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    prakriti: Mapped[str | None] = mapped_column(String(80), nullable=True)
    diagnosis: Mapped[str] = mapped_column(String(255))
    symptoms: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    ai_prescription: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    followup_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    patient: Mapped["Patient"] = relationship(back_populates="cases")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    date: Mapped[Date] = mapped_column(Date, index=True)
    time: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")


class PatientQuery(Base):
    __tablename__ = "patient_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    source_channel: Mapped[str] = mapped_column(String(30), default="app", index=True)
    query_text: Mapped[str] = mapped_column(Text)
    ai_response: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    ai_tag: Mapped[str] = mapped_column(String(20), default="NORMAL")
    fallback_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_sent: Mapped[int] = mapped_column(Integer, default=0)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    patient: Mapped["Patient"] = relationship(back_populates="patient_queries")
    doctor: Mapped["Doctor"] = relationship(back_populates="patient_queries")


class PendingReview(Base):
    __tablename__ = "pending_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    query_id: Mapped[int | None] = mapped_column(ForeignKey("patient_queries.id"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    ai_suggestion: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approved_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="pending_reviews")
    doctor: Mapped["Doctor"] = relationship(back_populates="pending_reviews")


class TongueAnalysis(Base):
    __tablename__ = "tongue_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    image_url: Mapped[str] = mapped_column(String(255), default="")
    analysis_text: Mapped[str] = mapped_column(Text, default="")
    prakriti_prediction: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BillingCode(Base):
    __tablename__ = "billing_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    icd_11_codes: Mapped[str] = mapped_column(Text, default="[]")
    ayush_code: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TelemedicineSession(Base):
    __tablename__ = "telemedicine_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    session_url: Mapped[str] = mapped_column(String(255), default="")
    provider: Mapped[str] = mapped_column(String(40), default="jitsi")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ConsultationSession(Base):
    __tablename__ = "consultation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    samhita_analyses: Mapped[list["SamhitaAnalysis"]] = relationship(back_populates="consultation")


class SamhitaAnalysis(Base):
    __tablename__ = "samhita_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultation_sessions.id"), nullable=True, index=True)
    symptoms: Mapped[str] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str] = mapped_column(String(10), default="")
    prakriti: Mapped[str] = mapped_column(String(50), default="Unknown")
    agni: Mapped[str] = mapped_column(String(50), default="Unknown")
    history: Mapped[str] = mapped_column(Text, default="None")
    dosha_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    herbal_formulations: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifestyle_regimen: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    classical_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    patient: Mapped["Patient | None"] = relationship(back_populates="samhita_analyses")
    consultation: Mapped["ConsultationSession | None"] = relationship(back_populates="samhita_analyses")
    dietary_items: Mapped[list["DietaryRecommendation"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    herbal_formulas: Mapped[list["HerbalFormula"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class DietaryRecommendation(Base):
    __tablename__ = "dietary_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("samhita_analyses.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    preparation: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped["SamhitaAnalysis"] = relationship(back_populates="dietary_items")


class HerbalFormula(Base):
    __tablename__ = "herbal_formulas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("samhita_analyses.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    sanskrit_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timing: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    precautions: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped["SamhitaAnalysis"] = relationship(back_populates="herbal_formulas")


class AyurvedicTerm(Base):
    __tablename__ = "ayurvedic_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    term: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    sanskrit_term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ipa_pronunciation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="", index=True)
    samhita: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    chapter: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verse_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verse_sanskrit: Mapped[str | None] = mapped_column(Text, nullable=True)
    verse_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    commentary_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commentary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    commentary_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_significance: Mapped[str | None] = mapped_column(Text, nullable=True)
    pronunciation_guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AyurTermCategory(Base):
    __tablename__ = "ayur_term_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PatientSamhitaQuery(Base):
    __tablename__ = "patient_samhita_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    term_id: Mapped[int | None] = mapped_column(ForeignKey("ayurvedic_terms.id"), nullable=True, index=True)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    patient: Mapped["Patient | None"] = relationship()
    term: Mapped["AyurvedicTerm | None"] = relationship()


class ConsultationMetric(Base):
    __tablename__ = "consultation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultation_sessions.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_used: Mapped[bool] = mapped_column(default=False)
    ai_voice_enabled: Mapped[bool] = mapped_column(default=False)
    ai_vision_enabled: Mapped[bool] = mapped_column(default=False)
    ai_prescription_enabled: Mapped[bool] = mapped_column(default=False)
    ai_diagnosis_enabled: Mapped[bool] = mapped_column(default=False)
    voice_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manual_time_saved_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DoctorActivityLog(Base):
    __tablename__ = "doctor_activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(80))
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class VoiceTranscript(Base):
    __tablename__ = "voice_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("consultation_sessions.id"), index=True)
    transcript: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    extracted_data: Mapped[str] = mapped_column(Text, default="{}")


class DeviceLog(Base):
    __tablename__ = "device_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    tested_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
