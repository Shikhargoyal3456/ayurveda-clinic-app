from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    secret_key: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "32-byte-encryption-key-here")
    jwt_secret: str = os.getenv("JWT_SECRET", "jwt-secret-key-change-here")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7
    password_min_length: int = 8
    password_bcrypt_rounds: int = 12
    rate_limit_per_ip: int = 100
    rate_limit_per_user: int = 200
    login_rate_limit: int = 5
    max_upload_size: int = 5 * 1024 * 1024
    allowed_upload_extensions: list[str] = ["jpg", "jpeg", "png", "gif", "pdf"]
    session_timeout_minutes: int = 30
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"
    allowed_origins: list[str] = ["http://localhost:8000", "https://kashai.example.com"]
    csp_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline' https://meet.jit.si; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


security_settings = SecuritySettings()
