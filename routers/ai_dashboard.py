from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor, Patient
from app.portal_auth import ensure_legacy_doctor_for_portal_user, get_portal_user
from services.ai_dashboard import (
    ACTION_CATALOG,
    ai_dashboard,
    build_doctor_dashboard_snapshot,
    build_patient_case_snapshot,
)


router = APIRouter(prefix="/api/ai-dashboard", tags=["AI Dashboard"])


def _resolve_request_doctor(request: Request, db: Session) -> Doctor:
    doctor_id = request.session.get("doctor_id")
    if doctor_id:
        doctor = db.get(Doctor, doctor_id)
        if doctor is not None:
            return doctor

    portal_user = get_portal_user(request, db)
    if portal_user is not None and getattr(getattr(portal_user, "role", None), "value", None) == "doctor":
        doctor = ensure_legacy_doctor_for_portal_user(db, portal_user)
        if doctor is not None:
            return doctor

    raise HTTPException(status_code=401, detail="Doctor authentication required.")


@router.get("/insights/{doctor_id}")
async def get_dashboard_insights(
    doctor_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    doctor = _resolve_request_doctor(request, db)
    if doctor.id != doctor_id:
        raise HTTPException(status_code=403, detail="You can only access your own dashboard insights.")

    snapshot = build_doctor_dashboard_snapshot(db, doctor.id)
    insights = await ai_dashboard.generate_dashboard_insights(doctor.id, snapshot)
    action_map = {
        item["action_key"]: {
            "label": ACTION_CATALOG[item["action_key"]]["label"],
            "url": ACTION_CATALOG[item["action_key"]]["url"],
            "reason": item["reason"],
        }
        for item in insights.get("dashboard_actions", [])
        if item.get("action_key") in ACTION_CATALOG
    }

    return {
        "success": True,
        "source": "ai",
        "data": {
            **insights,
            "action_map": action_map,
            "action_buttons": [
                {"text": value["label"], "action": value["url"], "reason": value["reason"]}
                for value in action_map.values()
            ],
        },
        "disclaimer": "AI-generated insights based on live patient, appointment, outcome, and follow-up data.",
    }


@router.get("/patient-recommendation/{patient_id}")
async def get_patient_recommendation(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    doctor = _resolve_request_doctor(request, db)
    patient = db.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="Patient not found.")

    case_data = build_patient_case_snapshot(db, patient_id)
    if case_data is None:
        raise HTTPException(status_code=404, detail="Patient case data not found.")

    recommendation = await ai_dashboard.generate_ai_recommendations(patient_id, case_data)
    return {
        "success": True,
        "source": "ai",
        "recommendation": recommendation,
    }
