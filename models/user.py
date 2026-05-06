from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    patient = "patient"
    doctor = "doctor"
    pharmacy_owner = "pharmacy_owner"
    lab_owner = "lab_owner"
    delivery_partner = "delivery_partner"
    admin = "admin"


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class VehicleType(str, Enum):
    bike = "bike"
    scooter = "scooter"
    cycle = "cycle"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole, native_enum=False), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    otp_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    otp_purpose: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    professional_document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SqlEnum(Gender, native_enum=False), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_avatar: Mapped[str | None] = mapped_column(String(10), nullable=True)
    relationship: Mapped[str] = mapped_column(String(50), default="Self", index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SqlEnum(Gender, native_enum=False), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pin_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consultation_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    available_days: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_time_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    available_time_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float] = mapped_column(Numeric(2, 1), default=0)
    total_consultations: Mapped[int] = mapped_column(Integer, default=0)


class PharmacyProfile(Base):
    __tablename__ = "pharmacy_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    pharmacy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(15), unique=True, nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_radius_km: Mapped[int] = mapped_column(Integer, default=5)
    minimum_order_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)


class LabProfile(Base):
    __tablename__ = "lab_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    lab_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accreditation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    is_home_collection_available: Mapped[bool] = mapped_column(Boolean, default=False)


class DeliveryProfile(Base):
    __tablename__ = "delivery_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(SqlEnum(VehicleType, native_enum=False))
    vehicle_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dl_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    current_latitude: Mapped[float | None] = mapped_column(Numeric(10, 8), nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float] = mapped_column(Numeric(2, 1), default=5)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    earnings: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
