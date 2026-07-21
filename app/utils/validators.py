from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import Sanitizer, validate_password_complexity


_SQLI_PATTERNS = re.compile(r"(union\s+select|drop\s+table|insert\s+into|update\s+\w+\s+set|--|/\*|\*/|;)", re.I)
_XSS_PATTERNS = re.compile(r"(<script|javascript:|onerror\s*=|onload\s*=|<iframe|<img)", re.I)


def contains_injection(value: str) -> bool:
    text = str(value or "")
    return bool(_SQLI_PATTERNS.search(text) or _XSS_PATTERNS.search(text))


class PatientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=160)
    email: str = Field(max_length=120)
    phone: str = Field(max_length=20)
    address: str = Field(max_length=255, default="")

    @field_validator("name", "address")
    @classmethod
    def sanitize_text_fields(cls, value: str) -> str:
        if contains_injection(value):
            raise ValueError("Potentially unsafe input detected")
        return Sanitizer.sanitize_html(value)

    @field_validator("email")
    @classmethod
    def sanitize_email(cls, value: str) -> str:
        return Sanitizer.sanitize_email(value)

    @field_validator("phone")
    @classmethod
    def sanitize_phone(cls, value: str) -> str:
        return Sanitizer.sanitize_phone(value)


def validate_secret_value(value: str) -> bool:
    return not contains_injection(value) and not any(token in value for token in ("sk-", "gsk_", "ghp_"))

