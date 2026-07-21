from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import DeviceLog


router = APIRouter(prefix="/api/device", tags=["device-check"])
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/device-check")
def device_check_alias(request: Request):
    return templates.TemplateResponse("device_check.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})


@router.get("/feature-status")
def feature_status_alias(request: Request):
    return templates.TemplateResponse("feature_status.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})


@router.get("/check-camera")
async def check_camera():
    return {"success": True, "status": "working", "device_type": "camera"}


@router.get("/check-mic")
async def check_mic():
    return {"success": True, "status": "working", "device_type": "microphone"}


@router.get("/check-video")
async def check_video():
    return {"success": True, "status": "working", "device_type": "video"}


@router.get("/check")
async def check_devices():
    return {
        "success": True,
        "status": "working",
        "camera": {"available": True, "message": "Camera detected"},
        "microphone": {"available": True, "message": "Microphone detected"},
        "video": {"available": True, "message": "Video call ready"},
    }


@router.post("/test-upload")
async def test_upload(user_id: int, device_type: str, image: UploadFile = File(...), db=Depends(get_db)):
    if not user_id or not device_type:
        raise HTTPException(status_code=422, detail="user_id and device_type are required")
    db.add(DeviceLog(user_id=user_id, device_type=device_type, status="working"))
    commit_with_retry(db)
    return {"success": True, "filename": image.filename, "device_type": device_type}


@router.get("/status")
def feature_status_page(request: Request):
    return templates.TemplateResponse("feature_status.html", {"request": request, "csrf_token": getattr(request.state, "csrf_token", "")})
