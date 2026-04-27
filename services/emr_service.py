from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Appointment, CaseSheet, Doctor, Patient
from models.emr import (
    EMRAssessment,
    EMRAuditLog,
    EMRConsentForm,
    EMRConsultation,
    EMRLabOrder,
    EMROutcome,
    EMRPatientProfile,
    EMRPrescription,
    EMRVital,
)
from models.payment import Payment


ICD11_SAMPLE_CODES = [
    {"code": "BA00", "diagnosis": "Essential hypertension", "category": "Cardiology", "chapter": "Diseases of the circulatory system"},
    {"code": "5A11", "diagnosis": "Type 2 diabetes mellitus", "category": "Endocrinology", "chapter": "Endocrine disorders"},
    {"code": "ME84", "diagnosis": "Gastro-oesophageal reflux disease", "category": "Gastroenterology", "chapter": "Digestive system disorders"},
    {"code": "FA20", "diagnosis": "Generalized anxiety disorder", "category": "Mental health", "chapter": "Mental and behavioural disorders"},
    {"code": "FA70", "diagnosis": "Insomnia disorder", "category": "Sleep medicine", "chapter": "Mental and behavioural disorders"},
    {"code": "FB53", "diagnosis": "Migraine", "category": "Neurology", "chapter": "Diseases of the nervous system"},
    {"code": "CA40", "diagnosis": "Osteoarthritis of knee", "category": "Orthopedics", "chapter": "Musculoskeletal disorders"},
    {"code": "1A00", "diagnosis": "Iron deficiency anaemia", "category": "Hematology", "chapter": "Blood disorders"},
]

DRUG_HERB_INTERACTIONS = {
    "Warfarin": ["Ashwagandha", "Guggulu", "Garlic"],
    "Metformin": ["Gurmar", "Fenugreek", "Cinnamon"],
    "Aspirin": ["Ginger", "Turmeric", "Guggulu"],
    "Levothyroxine": ["Soy", "Shatavari"],
    "Amlodipine": ["Arjuna", "Punarnava"],
}

PRAKRITI_QUESTION_BANK = [
    {"id": index + 1, "text": prompt, "vata": vata, "pitta": pitta, "kapha": kapha}
    for index, (prompt, vata, pitta, kapha) in enumerate(
        [
            ("Body frame", "Thin and light", "Moderate and warm", "Broad and steady"),
            ("Weight pattern", "Hard to gain", "Stable medium", "Easy to gain"),
            ("Skin quality", "Dry and cool", "Warm and sensitive", "Soft and oily"),
            ("Hair texture", "Dry and frizzy", "Fine and silky", "Thick and heavy"),
            ("Sleep quality", "Light and interrupted", "Moderate", "Deep and long"),
            ("Appetite", "Irregular", "Strong and sharp", "Slow but steady"),
            ("Digestion", "Variable", "Fast", "Slow"),
            ("Speech style", "Quick and lively", "Clear and direct", "Calm and measured"),
            ("Walking pace", "Fast", "Purposeful", "Slow and stable"),
            ("Tolerance to weather", "Dislikes cold", "Dislikes heat", "Dislikes damp"),
            ("Memory", "Learns fast forgets fast", "Learns clearly", "Learns slowly remembers long"),
            ("Emotional tendency", "Anxious", "Intense", "Attached and calm"),
            ("Energy pattern", "Bursts then fatigue", "Steady high output", "Slow endurance"),
            ("Bowel habit", "Dry or irregular", "Loose and frequent", "Well formed but sluggish"),
            ("Sweating", "Minimal", "Moderate to heavy", "Mild"),
            ("Voice", "Low or cracking", "Sharp and confident", "Deep and resonant"),
            ("Pulse feel", "Snake-like", "Frog-like", "Swan-like"),
            ("Cravings", "Warm foods", "Cool foods", "Light spicy foods"),
        ] * 3
    )
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_ur_number(patient_id: int) -> str:
    return f"UR-{datetime.now().strftime('%Y')}-{patient_id:05d}"


def ensure_emr_profile(db: Session, patient: Patient) -> EMRPatientProfile:
    profile = db.query(EMRPatientProfile).filter(EMRPatientProfile.patient_id == patient.id).first()
    if profile is not None:
        return profile

    profile = EMRPatientProfile(
        patient_id=patient.id,
        ur_number=generate_ur_number(patient.id),
        profile_data={
            "first_name": patient.name.split(" ")[0] if patient.name else "",
            "last_name": " ".join(patient.name.split(" ")[1:]) if patient.name and len(patient.name.split(" ")) > 1 else "",
            "mobile": patient.phone or "",
            "email": patient.email or "",
            "address": patient.address or "",
            "gender": patient.gender or "",
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "age": patient.age,
        },
        medical_history={
            "past_conditions": [],
            "immunizations": [],
            "medications": [],
            "family_risk_flags": [],
        },
        ayurveda_profile={
            "prakriti": "Vata-Pitta",
            "vikriti": "Vata aggravation",
            "agni": "Vishama",
            "ama": "Mild",
        },
        allergies=[],
        family_history=[],
        emergency_contact={"name": "", "phone": ""},
        consent_flags={"privacy": True, "telemedicine": False, "research": False},
    )
    db.add(profile)
    db.flush()
    return profile


def serialize_patient(patient: Patient, profile: EMRPatientProfile | None = None) -> dict[str, Any]:
    profile_data = profile.profile_data if profile else {}
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone,
        "email": patient.email,
        "address": patient.address,
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "ur_number": profile.ur_number if profile else None,
        "profile": profile_data,
        "medical_history": profile.medical_history if profile else {},
        "ayurveda_profile": profile.ayurveda_profile if profile else {},
        "allergies": profile.allergies if profile else [],
        "family_history": profile.family_history if profile else [],
        "emergency_contact": profile.emergency_contact if profile else {},
    }


def serialize_consultation(consultation: EMRConsultation) -> dict[str, Any]:
    return {
        "id": consultation.id,
        "patient_id": consultation.patient_id,
        "doctor_id": consultation.doctor_id,
        "appointment_id": consultation.appointment_id,
        "system_type": consultation.system_type,
        "status": consultation.status,
        "title": consultation.title,
        "chief_complaint": consultation.chief_complaint,
        "history_of_present_illness": consultation.history_of_present_illness,
        "notes": consultation.notes_json,
        "diagnoses": consultation.diagnosis_json,
        "treatment_plan": consultation.treatment_plan,
        "followup_date": consultation.followup_date.isoformat() if consultation.followup_date else None,
        "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
        "updated_at": consultation.updated_at.isoformat() if consultation.updated_at else None,
    }


def serialize_prescription(prescription: EMRPrescription) -> dict[str, Any]:
    return {
        "id": prescription.id,
        "consultation_id": prescription.consultation_id,
        "patient_id": prescription.patient_id,
        "doctor_id": prescription.doctor_id,
        "system_type": prescription.system_type,
        "status": prescription.status,
        "notes": prescription.notes,
        "items": prescription.items_json,
        "refill_count": prescription.refill_count,
        "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
    }


def serialize_lab_order(order: EMRLabOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "patient_id": order.patient_id,
        "doctor_id": order.doctor_id,
        "consultation_id": order.consultation_id,
        "lab_name": order.lab_name,
        "priority": order.priority,
        "status": order.status,
        "tests": order.tests_json,
        "results": order.results_json,
        "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }


def serialize_vital(vital: EMRVital) -> dict[str, Any]:
    payload = dict(vital.payload or {})
    payload.update({
        "id": vital.id,
        "recorded_at": vital.recorded_at.isoformat() if vital.recorded_at else None,
        "consultation_id": vital.consultation_id,
    })
    return payload


def build_patient_timeline(db: Session, patient_id: int) -> list[dict[str, Any]]:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return []
    entries: list[dict[str, Any]] = []
    for appointment in db.query(Appointment).filter(Appointment.patient_id == patient_id).all():
        entries.append({
            "type": "appointment",
            "title": appointment.reason or "Appointment",
            "date": appointment.date.isoformat() if appointment.date else None,
            "meta": appointment.status,
        })
    for case in db.query(CaseSheet).filter(CaseSheet.patient_id == patient_id).all():
        entries.append({
            "type": "case",
            "title": case.diagnosis,
            "date": case.created_at.isoformat() if case.created_at else None,
            "meta": case.prakriti,
        })
    for consultation in db.query(EMRConsultation).filter(EMRConsultation.patient_id == patient_id).all():
        entries.append({
            "type": f"consultation-{consultation.system_type}",
            "title": consultation.title,
            "date": consultation.created_at.isoformat() if consultation.created_at else None,
            "meta": consultation.status,
        })
    for prescription in db.query(EMRPrescription).filter(EMRPrescription.patient_id == patient_id).all():
        entries.append({
            "type": f"prescription-{prescription.system_type}",
            "title": f"{prescription.system_type.title()} prescription",
            "date": prescription.created_at.isoformat() if prescription.created_at else None,
            "meta": prescription.status,
        })
    entries.sort(key=lambda item: item.get("date") or "", reverse=True)
    return entries


def calculate_prakriti(answers: list[str]) -> dict[str, int]:
    scores = Counter({"vata": 0, "pitta": 0, "kapha": 0})
    for answer in answers:
        if answer in scores:
            scores[answer] += 1
    total = max(1, sum(scores.values()))
    return {key: round(value * 100 / total) for key, value in scores.items()}


def create_default_assessments(db: Session, patient_id: int, doctor_id: int, consultation_id: int | None = None) -> None:
    assessment_types = {
        "prakriti": {"vata": 38, "pitta": 34, "kapha": 28, "label": "Vata-Pitta"},
        "vikriti": {"vata": 56, "pitta": 24, "kapha": 20, "label": "Vata aggravation"},
        "agni": {"type": "vishama", "digestive_strength": 6},
        "ama": {"present": True, "severity": 4},
        "srotas": {"annavaha": "mild disturbance", "pranavaha": "clear"},
        "ashtavidha": {"nadi": "vata-pitta", "jihva": "coated", "mala": "irregular"},
    }
    for assessment_type, payload in assessment_types.items():
        exists = (
            db.query(EMRAssessment)
            .filter(
                EMRAssessment.patient_id == patient_id,
                EMRAssessment.assessment_type == assessment_type,
            )
            .first()
        )
        if exists is None:
            db.add(
                EMRAssessment(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    consultation_id=consultation_id,
                    assessment_type=assessment_type,
                    payload=payload,
                )
            )


def seed_emr_from_existing_records(db: Session) -> dict[str, int]:
    created_profiles = 0
    created_consultations = 0
    created_prescriptions = 0
    for patient in db.query(Patient).all():
        profile = db.query(EMRPatientProfile).filter(EMRPatientProfile.patient_id == patient.id).first()
        if profile is None:
            ensure_emr_profile(db, patient)
            created_profiles += 1
        create_default_assessments(db, patient.id, patient.doctor_id)
        if not db.query(EMRConsultation).filter(EMRConsultation.patient_id == patient.id).first():
            latest_case = (
                db.query(CaseSheet)
                .filter(CaseSheet.patient_id == patient.id)
                .order_by(CaseSheet.created_at.desc())
                .first()
            )
            title = latest_case.diagnosis if latest_case else "Imported consultation"
            system_type = "ayurveda" if patient.doctor and (patient.doctor.specialty or "").lower() == "ayurveda" else "modern"
            consultation = EMRConsultation(
                patient_id=patient.id,
                doctor_id=patient.doctor_id,
                system_type=system_type,
                status="finalized",
                title=title,
                chief_complaint=latest_case.symptoms if latest_case else "Imported from legacy patient record.",
                history_of_present_illness=latest_case.notes if latest_case else "",
                notes_json={
                    "subjective": latest_case.symptoms if latest_case else "",
                    "objective": "Imported legacy record",
                    "assessment": latest_case.diagnosis if latest_case else "General review",
                    "plan": latest_case.followup_notes if latest_case else "Continue follow-up",
                },
                diagnosis_json=[{"label": latest_case.diagnosis, "system": system_type}] if latest_case else [],
                treatment_plan=latest_case.followup_notes if latest_case else "Continue standard care plan.",
                followup_date=latest_case.followup_date if latest_case else None,
            )
            db.add(consultation)
            db.flush()
            created_consultations += 1
            if latest_case and latest_case.ai_prescription:
                try:
                    items = json.loads(latest_case.ai_prescription)
                    if not isinstance(items, list):
                        items = [{"name": str(latest_case.ai_prescription), "dosage": "As advised"}]
                except Exception:
                    items = [{"name": str(latest_case.ai_prescription), "dosage": "As advised"}]
                db.add(
                    EMRPrescription(
                        consultation_id=consultation.id,
                        patient_id=patient.id,
                        doctor_id=patient.doctor_id,
                        system_type=system_type,
                        items_json=items,
                        notes="Migrated from legacy AI prescription.",
                    )
                )
                created_prescriptions += 1
    return {
        "profiles": created_profiles,
        "consultations": created_consultations,
        "prescriptions": created_prescriptions,
    }


def get_doctor_dashboard_data(db: Session, doctor: Doctor) -> dict[str, Any]:
    today = date.today()
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).all()
    consultations = db.query(EMRConsultation).filter(EMRConsultation.doctor_id == doctor.id).all()
    vitals = db.query(EMRVital).filter(EMRVital.doctor_id == doctor.id).order_by(EMRVital.recorded_at.desc()).limit(8).all()
    labs = db.query(EMRLabOrder).filter(EMRLabOrder.doctor_id == doctor.id).order_by(EMRLabOrder.ordered_at.desc()).limit(8).all()
    outcomes = db.query(EMROutcome).join(Patient, Patient.id == EMROutcome.patient_id).filter(Patient.doctor_id == doctor.id).all()
    today_appointments = (
        db.query(Appointment)
        .filter(Appointment.date == today)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(Patient.doctor_id == doctor.id)
        .all()
    )
    pending_labs = [lab for lab in labs if lab.status != "completed"]
    followups_due = [consult for consult in consultations if consult.followup_date and consult.followup_date <= today]
    revenue_today = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor.id, Payment.date == today)
        .scalar()
        or 0
    )
    return {
        "today_appointments": today_appointments,
        "recent_patients": patients[:8],
        "pending_labs": pending_labs,
        "followups_due": followups_due[:8],
        "recent_vitals": vitals,
        "clinical_stats": {
            "total_patients": len(patients),
            "consultations": len(consultations),
            "outcomes": len(outcomes),
            "lab_backlog": len(pending_labs),
        },
        "revenue_today": float(revenue_today),
    }


def get_revenue_trend(db: Session, doctor_id: int, days: int = 7) -> list[dict[str, Any]]:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(Payment.date, func.coalesce(func.sum(Payment.amount), 0))
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor_id, Payment.date >= start)
        .group_by(Payment.date)
        .order_by(Payment.date.asc())
        .all()
    )
    revenue_map = {row[0]: float(row[1] or 0) for row in rows}
    return [
        {"date": (start + timedelta(days=index)).isoformat(), "amount": revenue_map.get(start + timedelta(days=index), 0.0)}
        for index in range(days)
    ]


def get_dosha_distribution(db: Session, doctor_id: int) -> dict[str, int]:
    totals = Counter({"vata": 0, "pitta": 0, "kapha": 0})
    assessments = (
        db.query(EMRAssessment)
        .filter(EMRAssessment.doctor_id == doctor_id, EMRAssessment.assessment_type == "prakriti")
        .all()
    )
    for assessment in assessments:
        payload = assessment.payload or {}
        totals["vata"] += int(payload.get("vata", 0) or 0)
        totals["pitta"] += int(payload.get("pitta", 0) or 0)
        totals["kapha"] += int(payload.get("kapha", 0) or 0)
    return dict(totals)


def get_data_quality_report(db: Session, doctor_id: int) -> dict[str, Any]:
    patients = db.query(Patient).filter(Patient.doctor_id == doctor_id).all()
    duplicates = defaultdict(list)
    missing = []
    for patient in patients:
        key = (patient.name.strip().lower(), patient.phone.strip())
        duplicates[key].append(patient.id)
        if not patient.phone or not patient.address or not patient.email:
            missing.append(patient)
    duplicate_sets = [ids for ids in duplicates.values() if len(ids) > 1]
    profiles_missing = (
        db.query(Patient)
        .outerjoin(EMRPatientProfile, EMRPatientProfile.patient_id == Patient.id)
        .filter(Patient.doctor_id == doctor_id, EMRPatientProfile.id.is_(None))
        .all()
    )
    return {
        "missing_contact": missing,
        "duplicate_sets": duplicate_sets,
        "missing_profiles": profiles_missing,
    }


def write_emr_audit_log(db: Session, user_id: int, action: str, record_type: str, record_id: int | None = None, patient_id: int | None = None, details: dict[str, Any] | None = None, ip_address: str = "", user_agent: str = "") -> EMRAuditLog:
    log = EMRAuditLog(
        user_id=user_id,
        patient_id=patient_id,
        action=action,
        record_type=record_type,
        record_id=record_id,
        details_json=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    db.flush()
    return log
