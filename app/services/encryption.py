from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class DataEncryption:
    def __init__(self) -> None:
        self.master_password = os.getenv("DATA_ENCRYPTION_KEY", "change-this-to-strong-password")
        self.salt = os.getenv("ENCRYPTION_SALT", "kash_ai_salt_2024").encode("utf-8")
        self.key = self._generate_key()
        self.cipher = Fernet(self.key)

    def _generate_key(self) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.master_password.encode("utf-8")))

    def encrypt(self, data):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self.cipher.encrypt(data)

    def decrypt(self, encrypted_data):
        decrypted = self.cipher.decrypt(encrypted_data)
        try:
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return decrypted.decode("utf-8")

    def encrypt_file(self, file_path: str | Path) -> Path:
        source_path = Path(file_path)
        encrypted_path = source_path.with_suffix(source_path.suffix + ".enc")
        encrypted_path.write_bytes(self.cipher.encrypt(source_path.read_bytes()))
        return encrypted_path

    def decrypt_file(self, enc_path: str | Path, output_path: str | Path | None = None) -> Path:
        encrypted_path = Path(enc_path)
        output = Path(output_path) if output_path else encrypted_path.with_suffix("")
        output.write_bytes(self.cipher.decrypt(encrypted_path.read_bytes()))
        return output
