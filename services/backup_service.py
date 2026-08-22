from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from services.encryption import DataEncryption


class BackupService:
    def __init__(self) -> None:
        self.encryption = DataEncryption()
        self.backup_dir = Path(os.getenv("BACKUP_DIR", str(settings.backups_dir))).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _database_path(self) -> Path:
        parsed = urlparse(settings.database_url)
        if parsed.scheme.startswith("sqlite"):
            path = (parsed.path or "").lstrip("/")
            if not path:
                return settings.base_dir / "ayurveda.db"
            return Path(path) if Path(path).is_absolute() else settings.base_dir / path
        return settings.base_dir / "ayurveda.db"

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        database_path = self._database_path()
        if not database_path.exists():
            return {"success": False, "error": f"Database file not found: {database_path}"}

        encrypted_path = self.encryption.encrypt_file(database_path)
        backup_file = self.backup_dir / f"backup_{timestamp}.enc"
        shutil.move(str(encrypted_path), backup_file)

        metadata = {
            "timestamp": timestamp,
            "file": str(backup_file),
            "size": backup_file.stat().st_size,
            "created_by": os.getenv("APP_NAME", "Kash AI"),
        }
        (self.backup_dir / f"metadata_{timestamp}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"success": True, "backup_file": str(backup_file), "timestamp": timestamp}

    def list_backups(self):
        backups = []
        for file_path in self.backup_dir.glob("*.enc"):
            backups.append(
                {
                    "file": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                }
            )
        return sorted(backups, key=lambda item: item["created"], reverse=True)

    def restore_backup(self, backup_file):
        backup_name = Path(str(backup_file)).name
        backup_path = (self.backup_dir / backup_name).resolve()
        if self.backup_dir not in backup_path.parents:
            return {"success": False, "error": "Invalid backup file path"}
        if not backup_path.exists():
            return {"success": False, "error": "Backup file not found"}
        restored = self.encryption.decrypt_file(backup_path, self._database_path())
        return {"success": True, "message": f"Database restored successfully to {restored}"}
