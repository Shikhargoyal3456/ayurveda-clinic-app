from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_doctor
from app.database import get_db
from app.models import Doctor
from services.ai_provider import generate_morning_brief


router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/morning-brief")
async def morning_brief(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    try:
        payload = await generate_morning_brief(doctor.id, db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Morning brief is temporarily unavailable.") from exc
    return JSONResponse({"success": True, "data": payload})
