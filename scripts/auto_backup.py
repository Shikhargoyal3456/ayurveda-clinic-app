from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from scripts.backup_db import backup_sqlite_db


logger = logging.getLogger(__name__)


def _cleanup_old_backups(backup_dir: Path, keep_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    for item in backup_dir.glob("*"):
        try:
            modified = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified < cutoff and item.is_file():
            item.unlink(missing_ok=True)


def _backup_postgres() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = settings.backups_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    sql_path = backup_dir / f"db_backup_{timestamp}.sql"
    env = os.environ.copy()
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise FileNotFoundError("pg_dump is required for PostgreSQL backups")
    command = [pg_dump, settings.database_url, "-f", str(sql_path)]
    subprocess.run(command, check=True, env=env)
    gz_path = sql_path.with_suffix(".sql.gz")
    with sql_path.open("rb") as source, gzip.open(gz_path, "wb") as target:
        shutil.copyfileobj(source, target)
    sql_path.unlink(missing_ok=True)
    return gz_path


def _upload_to_s3_if_configured(path: Path) -> None:
    bucket = os.getenv("S3_BACKUP_BUCKET", "").strip()
    if not bucket:
        return
    try:
        import boto3  # type: ignore

        client = boto3.client("s3")
        client.upload_file(str(path), bucket, f"database/{path.name}")
        logger.info("Uploaded backup %s to s3://%s/database/%s", path.name, bucket, path.name)
    except Exception as exc:  # pragma: no cover
        logger.warning("S3 upload skipped/failed for %s: %s", path, exc)


def backup_database() -> Path:
    if settings.database_url.startswith("sqlite"):
        backup_path = backup_sqlite_db(os.getenv("BACKUP_CLOUD_DIR", "").strip() or None)
    else:
        backup_path = _backup_postgres()
    _cleanup_old_backups(settings.backups_dir, settings.backup_retention_days)
    _upload_to_s3_if_configured(backup_path)
    return backup_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    path = backup_database()
    print(f"Backup completed: {path}")
