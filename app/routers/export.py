from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_doctor
from app.portal_auth import get_portal_user
from services.audit_service import AuditService
from services.export_service import ExportService


router = APIRouter(prefix="/api/export", tags=["export"])


def _current_actor(request: Request, db: Session):
    portal_user = get_portal_user(request, db)
    if portal_user is not None:
        return portal_user
    return get_current_doctor(request, db)


@router.get("/patients")
def export_patients(
    request: Request,
    format: str = Query("csv", pattern="^(csv)$"),
    db: Session = Depends(get_db),
):
    actor = _current_actor(request, db)
    if getattr(actor.role, "value", str(actor.role)) not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    export_service = ExportService(db)
    if getattr(actor.role, "value", str(actor.role)) != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access required")
    payload = export_service.export_patients_csv(actor)
    AuditService(db).log_action(request, "export_patients", "patients", details={"format": format}, user_id=actor.id, actor_role="doctor")
    return export_service.build_response(payload)


@router.get("/patients/{patient_id}")
def export_patient(
    patient_id: int,
    request: Request,
    format: str = Query("pdf", pattern="^(pdf)$"),
    db: Session = Depends(get_db),
):
    actor = _current_actor(request, db)
    if getattr(actor.role, "value", str(actor.role)) not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    export_service = ExportService(db)
    if getattr(actor.role, "value", str(actor.role)) != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access required for individual patient PDF")
    payload = export_service.export_patient_pdf(actor, patient_id)
    AuditService(db).log_action(request, "export_patient", "patient", patient_id, {"format": format}, actor.id, getattr(actor.role, "value", str(actor.role)))
    return export_service.build_response(payload)


@router.get("/prescriptions/{prescription_id}")
def export_prescription(
    prescription_id: int,
    request: Request,
    format: str = Query("pdf", pattern="^(pdf)$"),
    db: Session = Depends(get_db),
):
    actor = _current_actor(request, db)
    if getattr(actor.role, "value", str(actor.role)) not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    export_service = ExportService(db)
    if getattr(actor.role, "value", str(actor.role)) != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access required for prescription PDF")
    payload = export_service.export_prescription_pdf(actor, prescription_id)
    AuditService(db).log_action(request, "export_prescription", "prescription", prescription_id, {"format": format}, actor.id, getattr(actor.role, "value", str(actor.role)))
    return export_service.build_response(payload)


@router.get("/all-data")
def export_all_data(
    request: Request,
    db: Session = Depends(get_db),
):
    export_service = ExportService(db)
    portal_user = get_portal_user(request, db)
    if portal_user is not None and getattr(portal_user.role, "value", str(portal_user.role)) == "admin":
        payload = export_service.export_all_data()
        AuditService(db).log_action(request, "export_all_data", "clinic", details={}, user_id=portal_user.id, actor_role="admin")
        return export_service.build_response(payload)
    doctor = get_current_doctor(request, db)
    payload = export_service.export_all_data(doctor)
    AuditService(db).log_action(request, "export_all_data", "clinic", details={}, user_id=doctor.id, actor_role="doctor")
    return export_service.build_response(payload)
