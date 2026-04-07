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


class CaseSheet(Base):
    __tablename__ = "case_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    prakriti: Mapped[str] = mapped_column(String(80))
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
