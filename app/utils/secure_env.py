from __future__ import annotations

import os
from typing import Optional


class SecureEnv:
    REQUIRED_VARS = {"SECRET_KEY", "JWT_SECRET", "ENCRYPTION_KEY", "DATABASE_URL"}

    @staticmethod
    def validate_secret_key(key: str) -> bool:
        return len(key or "") >= 32

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> str:
        value = os.getenv(key, default)
        if key in SecureEnv.REQUIRED_VARS and not value:
            raise ValueError(f"Required environment variable '{key}' is missing")
        if key in {"SECRET_KEY", "JWT_SECRET", "ENCRYPTION_KEY"} and value and not SecureEnv.validate_secret_key(value):
            raise ValueError(f"{key} must be at least 32 characters")
        return str(value or "")

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        try:
            return int(os.getenv(key, str(default)).strip())
        except ValueError:
            return default


secure_env = SecureEnv()
