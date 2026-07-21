from __future__ import annotations

import threading
import time
from datetime import datetime

try:
    import schedule
except Exception:  # pragma: no cover
    schedule = None

from app.config import settings
from services.backup_service import BackupService


class BackupScheduler:
    def __init__(self) -> None:
        self.backup_service = BackupService()
        self.running = False

    def run_backup(self):
        print(f"[{datetime.now()}] Running scheduled backup...")
        return self.backup_service.create_backup()

    def start(self):
        self.running = True
        if schedule is not None:
            schedule.every(max(1, int(settings.backup_interval_hours or 6))).hours.do(self.run_backup)
            schedule.every().day.at("00:00").do(self.run_backup)
            print(f"[BackupScheduler] Started. Backups every {max(1, int(settings.backup_interval_hours or 6))} hours and at midnight.")
            while self.running:
                schedule.run_pending()
                time.sleep(60)
        else:
            print("[BackupScheduler] schedule package unavailable. Running fallback interval loop.")
            while self.running:
                self.run_backup()
                time.sleep(max(1, int(settings.backup_interval_hours or 6)) * 60 * 60)

    def start_background(self):
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.running = False
