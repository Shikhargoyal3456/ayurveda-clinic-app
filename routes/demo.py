from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_doctor, set_flash, verify_csrf
from app.database import get_db
from app.demo_seed import create_demo_data, reset_demo_data
from app.models import Doctor


router = APIRouter(tags=["demo"])


@router.get("/demo/setup")
def setup_demo_data(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    seeded = create_demo_data(db, doctor)
    set_flash(
        request,
        (
            f"Demo data ready: {seeded['patients']} patients, {seeded['prescriptions']} prescriptions, "
            f"{seeded['payments']} payments, {seeded['outcomes']} outcomes."
        ),
        "success",
    )
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/demo/reset")
def reset_demo_workspace(
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    deleted = reset_demo_data(db, doctor)
    if deleted["patients"] == 0:
        set_flash(request, "No demo data was found for this account.", "info")
    else:
        set_flash(request, f"Demo data reset for {deleted['patients']} patients.", "success")
    return RedirectResponse(url="/dashboard", status_code=303)
