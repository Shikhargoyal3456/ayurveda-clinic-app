from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from services.backup_scheduler import BackupScheduler
from services.backup_service import BackupService
from app.database import get_db
from app.portal_auth import get_portal_user


router = APIRouter(prefix="/api/backup", tags=["backup"])
backup_service = BackupService()
backup_scheduler = BackupScheduler()


def _require_admin(request: Request, db: Session) -> None:
    user = get_portal_user(request, db)
    if user is None or getattr(user.role, "value", str(user.role)) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/create")
def create_backup(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    result = backup_service.create_backup()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result


@router.get("/list")
def list_backups(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    return {"success": True, "backups": backup_service.list_backups()}


@router.post("/restore")
def restore_backup(request: Request, backup_file: str, db: Session = Depends(get_db)):
    _require_admin(request, db)
    result = backup_service.restore_backup(backup_file)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Restore failed"))
    return result
