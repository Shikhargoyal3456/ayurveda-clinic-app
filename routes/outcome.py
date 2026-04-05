from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import CaseSheet, Doctor, Patient
from models.outcome import Outcome


templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["outcomes"])


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/patients/{patient_id}/outcomes")
def patient_outcomes(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    outcomes = (
        db.query(Outcome)
        .filter(Outcome.patient_id == patient.id)
        .order_by(Outcome.date.desc(), Outcome.id.desc())
        .all()
    )
    cases = db.query(CaseSheet).filter(CaseSheet.patient_id == patient.id).order_by(CaseSheet.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "outcomes/list.html",
        {
            "patient": patient,
            "outcomes": outcomes,
            "cases": cases,
            "flash": pop_flash(request),
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/outcomes/add")
def add_outcome(
    request: Request,
    patient_id: int = Form(...),
    case_id: int | None = Form(default=None),
    improvement_status: str = Form("Not recorded yet"),
    symptom_score: int = Form(...),
    notes: str = Form("", max_length=3000),
    outcome_date: str = Form(""),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    raw_status = improvement_status.strip()
    normalized_status = "Not recorded yet" if raw_status.lower() == "not recorded yet" else raw_status.title()
    if normalized_status not in {"Better", "Same", "Worse", "Not recorded yet"}:
        set_flash(request, "Improvement status must be Better, Same, Worse, or Not recorded yet.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/outcomes", status_code=303)
    if symptom_score < 1 or symptom_score > 10:
        set_flash(request, "Symptom score must be between 1 and 10.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/outcomes", status_code=303)

    linked_case_id = None
    if case_id:
        case = db.query(CaseSheet).filter(CaseSheet.id == case_id, CaseSheet.patient_id == patient.id).first()
        if case is None:
            set_flash(request, "Selected case could not be found for this patient.", "danger")
            return RedirectResponse(url=f"/patients/{patient.id}/outcomes", status_code=303)
        linked_case_id = case.id

    try:
        parsed_date = datetime.strptime(outcome_date, "%Y-%m-%d").date() if outcome_date else date.today()
    except ValueError:
        set_flash(request, "Outcome date must use the YYYY-MM-DD format.", "danger")
        return RedirectResponse(url=f"/patients/{patient.id}/outcomes", status_code=303)

    outcome = Outcome(
        patient_id=patient.id,
        case_id=linked_case_id,
        improvement_status=normalized_status,
        symptom_score=symptom_score,
        notes=notes.strip(),
        date=parsed_date,
    )
    db.add(outcome)
    commit_with_retry(db)
    write_audit_event("outcome_added", request, outcome_id=outcome.id, patient_id=patient.id)
    set_flash(request, "Outcome saved.", "success")
    return RedirectResponse(url=f"/patients/{patient.id}/outcomes", status_code=303)
