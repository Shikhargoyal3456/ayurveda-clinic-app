from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    remember_me: bool = False

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return value.strip()


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=100)
    role: str = Field(..., pattern=r"^(doctor|patient)$")
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email address")
        return email


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern=r"^(male|female|other)$")
    phone: str = Field(..., pattern=r"^[0-9]{10}$")
    email: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        email = value.strip()
        if not email:
            return None
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email address")
        return email


class PrescriptionCreate(BaseModel):
    patient_id: int = Field(..., gt=0)
    case_sheet_id: int = Field(..., gt=0)
    medicines: list[dict[str, Any]] = Field(..., min_length=1)
    instructions: str = Field(..., min_length=1, max_length=1000)
    follow_up_days: int = Field(..., ge=1, le=90)


class AppointmentCreate(BaseModel):
    patient_id: int = Field(..., gt=0)
    date: datetime
    time: str = Field(..., pattern=r"^([0-9]{2}):([0-9]{2})$")
    duration_minutes: int = Field(..., ge=15, le=120)
    notes: Optional[str] = Field(None, max_length=500)


class CaseSheetCreate(BaseModel):
    patient_id: int = Field(..., gt=0)
    symptoms: list[str] = Field(..., min_length=1)
    diagnosis: str = Field(..., min_length=1, max_length=500)
    duration: str = Field(..., min_length=1, max_length=50)
    history: Optional[str] = Field(None, max_length=1000)
    treatment_plan: Optional[str] = Field(None, max_length=1000)


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    patient_id: Optional[int] = Field(None, gt=0)
    context: str = Field(default="doctor_assistant")


class AIFeedbackCreate(BaseModel):
    consultation_id: int = Field(..., gt=0)
    feature_type: str = Field(..., pattern=r"^(diagnosis|prescription|voice|vision)$")
    ai_suggestion: str = Field(..., min_length=1)
    doctor_final: str = Field(..., min_length=1)
    was_accepted: bool = False
    modified: bool = False
    accuracy_score: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None
