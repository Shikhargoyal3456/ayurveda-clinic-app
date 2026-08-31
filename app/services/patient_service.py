from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from app.models import CaseSheet, Patient
from models.medicine import MedicineOrder
from models.outcome import Outcome
from models.payment import Payment
from models.prescription import Prescription

from routers.pharmacy import _is_repeat_order, _load_order_items

def _iso(value):
    return value.isoformat() if value else None

def get_patient_insights(db: Session, patient_id: int) -> dict[str, object]:
    try:
        patient = db.get(Patient, patient_id)
        if patient is None or not patient.phone:
            return {
                "total_orders": 0,
                "last_order_date": None,
                "repeat_count": 0,
                "most_common_medicines": [],
            }
        orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.patient_phone == patient.phone)
            .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
            .all()
        )
        medicine_counter: Counter[str] = Counter()
        repeat_count = 0
        for order in orders:
            if _is_repeat_order(order):
                repeat_count += 1
            for item in _load_order_items(order):
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if name:
                        medicine_counter[name] += int(item.get("qty", 1) or 1)
        return {
            "total_orders": len(orders),
            "last_order_date": _iso(orders[0].created_at) if orders else None,
            "repeat_count": repeat_count,
            "most_common_medicines": [
                {"name": name, "count": count}
                for name, count in medicine_counter.most_common(3)
            ],
        }
    except Exception as exc:
        __import__("logging").getLogger(__name__).exception("Patient insights failed for patient_id=%s: %s", patient_id, exc)
        return {
            "total_orders": 0,
            "last_order_date": None,
            "repeat_count": 0,
            "most_common_medicines": [],
        }

def get_patient_timeline(db: Session, patient_id: int) -> dict[str, Any]:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return {"success": False, "error": "Patient not found"}

    cases = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient.id)
        .order_by(CaseSheet.created_at.desc())
        .all()
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == patient.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .all()
    )
    medicine_orders = []
    if patient.phone:
        medicine_orders = (
            db.query(MedicineOrder)
            .filter(MedicineOrder.patient_phone == patient.phone)
            .order_by(MedicineOrder.created_at.desc(), MedicineOrder.id.desc())
            .all()
        )
    payments = (
        db.query(Payment)
        .filter(Payment.patient_id == patient.id)
        .order_by(Payment.date.desc(), Payment.id.desc())
        .all()
    )
    outcomes = (
        db.query(Outcome)
        .filter(Outcome.patient_id == patient.id)
        .order_by(Outcome.date.desc(), Outcome.id.desc())
        .all()
    )

    return {
        "success": True,
        "data": {
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "phone": patient.phone,
                "created_at": _iso(patient.created_at),
            },
            "insights": get_patient_insights(db, patient.id),
            "cases": [
                {
                    "id": case.id,
                    "diagnosis": case.diagnosis,
                    "symptoms": case.symptoms,
                    "followup_date": _iso(case.followup_date),
                    "created_at": _iso(case.created_at),
                }
                for case in cases
            ],
            "prescriptions": [
                {
                    "id": prescription.id,
                    "diagnosis": prescription.diagnosis,
                    "medicines": prescription.medicines,
                    "follow_up_days": prescription.follow_up_days,
                    "created_at": _iso(prescription.created_at),
                }
                for prescription in prescriptions
            ],
            "medicine_orders": [
                {
                    "id": order.id,
                    "status": order.status,
                    "payment_status": order.payment_status,
                    "paid_at": _iso(order.paid_at),
                    "total_amount": order.total_amount,
                    "created_at": _iso(order.created_at),
                    "source": _order_source(order),
                    "is_repeat_order": _is_repeat_order(order),
                }
                for order in medicine_orders
            ],
            "payments": [
                {
                    "id": payment.id,
                    "amount": float(payment.amount or 0),
                    "status": payment.status,
                    "date": _iso(payment.date),
                    "payment_method": payment.payment_method,
                }
                for payment in payments
            ],
            "outcomes": [
                {
                    "id": outcome.id,
                    "case_id": outcome.case_id,
                    "improvement_status": outcome.improvement_status,
                    "symptom_score": outcome.symptom_score,
                    "notes": outcome.notes,
                    "date": _iso(outcome.date),
                }
                for outcome in outcomes
            ],
        }
    }
