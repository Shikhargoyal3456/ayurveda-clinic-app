from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Patient
from app.portal_auth import get_portal_user
from models.patient_link import PatientAccountLink
from services.audit_service import AuditService
from app.auth import ensure_csrf_token


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["patient-linking"])


@router.get("/new/claim-patient")
def claim_patient_page(request: Request, db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is None:
        return RedirectResponse(url="/new/login", status_code=303)
    return templates.TemplateResponse(
        "new_claim_patient.html",
        {"request": request, "user": user, "csrf_token": ensure_csrf_token(request)},
    )


@router.post("/new/claim-patient")
def claim_patient_submit(
    request: Request,
    claim_value: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_portal_user(request, db)
    if user is None:
        return RedirectResponse(url="/new/login", status_code=303)
    token = str(claim_value).strip()
    patient = (
        db.query(Patient)
        .filter(
            or_(
                Patient.email == token,
                Patient.phone == token,
                Patient.name.ilike(token),
            )
        )
        .first()
    )
    if patient is None:
        return RedirectResponse(url="/new/claim-patient?message=No matching record found", status_code=303)
    link = db.query(PatientAccountLink).filter(PatientAccountLink.user_id == user.id).first()
    if link is None:
        link = PatientAccountLink(user_id=user.id, patient_id=patient.id, match_type="manual")
        db.add(link)
    else:
        link.patient_id = patient.id
        link.match_type = "manual"
    db.commit()
    AuditService(db).log_action(request, "patient_claimed", "patient", patient.id, {"claim_value": token}, user.id, "patient")
    return RedirectResponse(url="/new/patient?message=Health record linked successfully", status_code=303)
