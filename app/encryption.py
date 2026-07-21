from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.security_config import security_settings


class EncryptionManager:
    def __init__(self) -> None:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kash-ai-salt-2026",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(security_settings.encryption_key.encode()))
        self.cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        if not data:
            return ""
        encrypted = self.cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            return self.cipher.decrypt(decoded).decode()
        except Exception:
            return ""


encryption = EncryptionManager()
