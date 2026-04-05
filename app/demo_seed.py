from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import commit_with_retry
from app.models import Appointment, CaseSheet, Doctor, Patient
from models.outcome import Outcome
from models.payment import Payment
from models.prescription import Prescription


def reset_demo_data(db: Session, doctor: Doctor) -> dict[str, int]:
    email_prefix = f"demo-clinic-{doctor.id}"
    demo_patients = (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .all()
    )
    patient_ids = [patient.id for patient in demo_patients]
    if not patient_ids:
        return {"patients": 0}

    db.query(Outcome).filter(Outcome.patient_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(Payment).filter(Payment.patient_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(Prescription).filter(Prescription.patient_id.in_(patient_ids)).delete(synchronize_session=False)

    for patient in demo_patients:
        db.delete(patient)

    commit_with_retry(db)
    return {"patients": len(patient_ids)}


def create_demo_data(db: Session, doctor: Doctor) -> dict[str, int]:
    """Seed a small, idempotent clinic dataset for product demos."""
    email_prefix = f"demo-clinic-{doctor.id}"
    existing_patients = {
        patient.email: patient
        for patient in (
            db.query(Patient)
            .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
            .order_by(Patient.id.asc())
            .all()
        )
    }
    patient_blueprints = [
        {
            "name": "Anaya Mehta",
            "age": 29,
            "gender": "Female",
            "phone": "9876543210",
            "email": f"{email_prefix}-1@demo.local",
            "address": "Indiranagar, Bengaluru",
        },
        {
            "name": "Rohan Iyer",
            "age": 41,
            "gender": "Male",
            "phone": "9876543211",
            "email": f"{email_prefix}-2@demo.local",
            "address": "HSR Layout, Bengaluru",
        },
        {
            "name": "Meera Nair",
            "age": 35,
            "gender": "Female",
            "phone": "9876543212",
            "email": f"{email_prefix}-3@demo.local",
            "address": "Koramangala, Bengaluru",
        },
    ]
    for blueprint in patient_blueprints:
        if blueprint["email"] in existing_patients:
            continue
        patient = Patient(doctor_id=doctor.id, **blueprint)
        db.add(patient)
        db.flush()
        existing_patients[patient.email] = patient

    patient_records = [
        existing_patients[f"{email_prefix}-1@demo.local"],
        existing_patients[f"{email_prefix}-2@demo.local"],
        existing_patients[f"{email_prefix}-3@demo.local"],
    ]

    existing_cases = (
        db.query(Patient)
        .join(CaseSheet, CaseSheet.patient_id == Patient.id, isouter=False)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .count()
    )
    if existing_cases < 2:
        case_records = [
            CaseSheet(
                patient_id=patient_records[0].id,
                prakriti="Vata-Pitta",
                diagnosis="Stress-linked insomnia",
                symptoms="Light sleep, anxiety, dry skin, fatigue, late-night wakefulness.",
                notes="Demo case focused on follow-up and prescription workflows.",
                followup_date=date.today() + timedelta(days=5),
                followup_notes="Check sleep duration and evening routine adherence.",
            ),
            CaseSheet(
                patient_id=patient_records[1].id,
                prakriti="Kapha-Pitta",
                diagnosis="Digestive imbalance",
                symptoms="Bloating, heaviness after meals, mild acidity, afternoon lethargy.",
                notes="Demo case used for outcomes and payment tracking.",
                followup_date=date.today() + timedelta(days=7),
                followup_notes="Review appetite, bowel regularity, and exercise consistency.",
            ),
        ]
        db.add_all(case_records)
        db.flush()

    existing_cases = (
        db.query(CaseSheet)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .order_by(CaseSheet.id.asc())
        .all()
    )

    existing_appointments = (
        db.query(Appointment)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .count()
    )
    if existing_appointments < 3:
        db.add_all(
            [
                Appointment(
                    patient_id=patient_records[0].id,
                    date=date.today(),
                    time="10:00",
                    reason="Sleep review",
                    status="scheduled",
                ),
                Appointment(
                    patient_id=patient_records[1].id,
                    date=date.today(),
                    time="12:30",
                    reason="Digestive follow-up",
                    status="scheduled",
                ),
                Appointment(
                    patient_id=patient_records[2].id,
                    date=date.today() + timedelta(days=1),
                    time="16:00",
                    reason="Initial consultation",
                    status="scheduled",
                ),
            ]
        )

    existing_prescriptions = (
        db.query(Prescription)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .count()
    )
    if existing_prescriptions < 2:
        db.add_all(
            [
                Prescription(
                    patient_id=patient_records[0].id,
                    doctor_id=doctor.id,
                    diagnosis="Nidranasha with aggravated Vata",
                    medicines=[
                        {"name": "Ashwagandha Churna", "dosage": "1 tsp", "frequency": "Twice daily"},
                        {"name": "Brahmi Ghrita", "dosage": "5 ml", "frequency": "At bedtime"},
                    ],
                    advice="Warm dinner, screen-free wind-down, and abhyanga before sleep.",
                    follow_up_days=7,
                ),
                Prescription(
                    patient_id=patient_records[1].id,
                    doctor_id=doctor.id,
                    diagnosis="Agnimandya with mild amlapitta",
                    medicines=[
                        {"name": "Avipattikar Churna", "dosage": "1 tsp", "frequency": "After lunch and dinner"},
                        {"name": "Guduchi Satva", "dosage": "500 mg", "frequency": "Once daily"},
                    ],
                    advice="Lighter evening meals, avoid cold drinks, and walk after meals.",
                    follow_up_days=5,
                ),
            ]
        )

    existing_payments = (
        db.query(Payment)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .count()
    )
    if existing_payments < 2:
        db.add_all(
            [
                Payment(
                    patient_id=patient_records[0].id,
                    amount=Decimal("1200.00"),
                    status="paid",
                    date=date.today(),
                ),
                Payment(
                    patient_id=patient_records[1].id,
                    amount=Decimal("800.00"),
                    status="unpaid",
                    date=date.today(),
                ),
            ]
        )

    existing_outcomes = (
        db.query(Outcome)
        .join(Patient)
        .filter(Patient.doctor_id == doctor.id, Patient.email.like(f"{email_prefix}-%"))
        .count()
    )
    if existing_outcomes < 2:
        db.add_all(
            [
                Outcome(
                    patient_id=patient_records[0].id,
                    case_id=existing_cases[0].id if existing_cases else None,
                    improvement_status="Better",
                    symptom_score=4,
                    notes="Sleep onset improved after evening routine changes.",
                    date=date.today(),
                ),
                Outcome(
                    patient_id=patient_records[1].id,
                    case_id=existing_cases[1].id if len(existing_cases) > 1 else None,
                    improvement_status="Same",
                    symptom_score=6,
                    notes="Bloating reduced slightly but appetite still inconsistent.",
                    date=date.today(),
                ),
            ]
        )

    commit_with_retry(db)
    return {"patients": 3, "prescriptions": 2, "payments": 2, "outcomes": 2}
