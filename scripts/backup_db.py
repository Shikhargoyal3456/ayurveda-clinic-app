from __future__ import annotations

import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import settings


logger = logging.getLogger(__name__)


def _sqlite_db_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Backup script supports SQLite databases only.")
    raw_path = database_url.removeprefix(prefix)
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = settings.base_dir / db_path
    return db_path


def _cleanup_old_backups(backup_dir: Path, keep_days: int = 7) -> None:
    backups = sorted(backup_dir.glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    for stale_backup in backups[keep_days:]:
        stale_backup.unlink(missing_ok=True)


def backup_sqlite_db(cloud_target: str | None = None) -> Path:
    source_path = _sqlite_db_path(settings.database_url)
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {source_path}")

    backup_dir = settings.backups_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = backup_dir / f"{source_path.stem}_{timestamp}.zip"
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_path, arcname=source_path.name)
    _cleanup_old_backups(backup_dir)

    if cloud_target:
        cloud_dir = Path(cloud_target)
        cloud_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive_path, cloud_dir / archive_path.name)
        logger.info("Copied backup archive to cloud target %s", cloud_dir)

    logger.info("Backup created at %s", archive_path)
    return archive_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    backup_path = backup_sqlite_db()
    print(f"Backup created at {backup_path}")
