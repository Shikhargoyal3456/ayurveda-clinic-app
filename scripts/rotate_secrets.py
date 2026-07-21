"""
Secret rotation script for Kash AI
Run: python scripts/rotate_secrets.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import secrets


def generate_secure_key(length: int = 32) -> str:
    return secrets.token_hex(length)


def rotate_secrets() -> None:
    print("ROTATING SECRETS...")
    print("=" * 50)
    secret_key = generate_secure_key()
    jwt_secret = generate_secure_key()
    encryption_key = generate_secure_key()
    admin_token = generate_secure_key()
    print("NEW SECRETS GENERATED:")
    print(f"SECRET_KEY={secret_key}")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"ENCRYPTION_KEY={encryption_key[:32]}")
    print(f"ADMIN_API_TOKEN={admin_token}")
    print("Update .env, restart the server, and revoke old keys immediately.")
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    with (logs_dir / "secret_rotation.txt").open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat()}] Secrets rotated\n")
    print("Rotation logged to logs/secret_rotation.txt")


if __name__ == "__main__":
    rotate_secrets()
