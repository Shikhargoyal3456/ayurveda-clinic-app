from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, get_current_doctor, pop_flash, set_flash, verify_csrf
from app.config import settings
from app.database import commit_with_retry, get_db
from app.models import Appointment, Doctor, Patient
from app.portal_auth import normalize_doctor_type
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
from services.emr_service import (
    DRUG_HERB_INTERACTIONS,
    ICD11_SAMPLE_CODES,
    PRAKRITI_QUESTION_BANK,
    build_patient_timeline,
    calculate_prakriti,
    create_default_assessments,
    ensure_emr_profile,
    generate_ur_number,
    get_data_quality_report,
    get_doctor_dashboard_data,
    get_dosha_distribution,
    get_revenue_trend,
    seed_emr_from_existing_records,
    serialize_consultation,
    serialize_lab_order,
    serialize_patient,
    serialize_prescription,
    write_emr_audit_log,
)
from services.diet_ai import generate_diet_plan
from shared.template_engine import render_template

templates = Jinja2Templates(directory=str(settings.templates_dir))
router = APIRouter(tags=["emr"])

AYURVEDA_FORMULATION_LIBRARY = [
    {"name": "Avipattikar Churna", "use": "Acidity and pitta balance", "anupana": "Warm water"},
    {"name": "Ashwagandha Lehyam", "use": "Stress support", "anupana": "Milk"},
    {"name": "Triphala Churna", "use": "Bowel support", "anupana": "Warm water at bedtime"},
    {"name": "Yogaraja Guggulu", "use": "Pain and stiffness", "anupana": "Warm water"},
]
MODERN_DRUG_LIBRARY = [
    {"name": "Amlodipine", "class": "Calcium channel blocker", "strengths": ["2.5 mg", "5 mg", "10 mg"]},
    {"name": "Metformin", "class": "Biguanide", "strengths": ["500 mg", "850 mg", "1000 mg"]},
    {"name": "Pantoprazole", "class": "Proton pump inhibitor", "strengths": ["20 mg", "40 mg"]},
    {"name": "Paracetamol", "class": "Analgesic", "strengths": ["500 mg", "650 mg"]},
]
HELP_TERMS = {
    "prakriti": "Innate constitution of Vata, Pitta, and Kapha.",
    "vikriti": "Current dosha imbalance pattern.",
    "agni": "Digestive and metabolic fire.",
    "ama": "Undigested toxic byproducts that disturb balance.",
    "srotas": "Functional body channels described in Ayurveda.",
    "anupana": "Vehicle taken with medicine such as honey or warm water.",
    "kala": "Recommended timing for medicine intake.",
}
SECTION_LINKS = [
    ("doctor_dashboard", "/emr/doctor-dashboard", "Doctor Dashboard", "fa-house-medical"),
    ("patient_registry", "/emr/patient-registry", "Patient Registry", "fa-id-card-clip"),
    ("ambient_scribe", "/emr/ambient-scribe", "AI Scribe", "fa-microphone-lines"),
    ("clinical_reporting", "/emr/clinical-reporting", "Clinical Reports", "fa-chart-line"),
    ("lab_dashboard", "/emr/lab-dashboard", "Lab Dashboard", "fa-flask-vial"),
    ("clinical_decisions", "/emr/clinical-decisions", "Decision Support", "fa-staff-snake"),
    ("billing_integration", "/emr/billing-integration", "Billing", "fa-file-invoice-rupee"),
    ("test_emr", "/emr/test-emr", "Test EMR", "fa-vial-circle-check"),
]


def _is_admin(doctor: Doctor) -> bool:
    allowed_admins = [item.strip().lower() for item in settings.admin_usernames if item.strip()]
    return (doctor.username or "").strip().lower() in allowed_admins or (not settings.is_production and int(getattr(doctor, "id", 0) or 0) == 1)


def require_doctor_role(doctor: Doctor = Depends(get_current_doctor)) -> Doctor:
    if not doctor:
        raise HTTPException(status_code=403, detail="Doctor access required.")
    return doctor


def require_ayurveda_doctor(doctor: Doctor = Depends(get_current_doctor)) -> Doctor:
    specialty = (doctor.specialty or "ayurveda").lower()
    if specialty not in {"ayurveda"} and not _is_admin(doctor):
        raise HTTPException(status_code=403, detail="Ayurveda doctor access required.")
    return doctor


def require_modern_doctor(doctor: Doctor = Depends(get_current_doctor)) -> Doctor:
    specialty = (doctor.specialty or "").lower()
    if specialty not in {"modern_medicine", "dental", "physiotherapy"} and not _is_admin(doctor):
        raise HTTPException(status_code=403, detail="Modern medicine doctor access required.")
    return doctor


def require_integrated_access(doctor: Doctor = Depends(get_current_doctor)) -> Doctor:
    specialty = (doctor.specialty or "").lower()
    if specialty not in {"ayurveda", "modern_medicine", "homeopathy", "dental", "physiotherapy"} and not _is_admin(doctor):
        raise HTTPException(status_code=403, detail="Clinical access required.")
    return doctor


def _consultation_entry_url_for_doctor(doctor: Doctor) -> str:
    specialty = (doctor.specialty or "ayurveda").strip().lower()
    if specialty in {"modern_medicine", "dental", "physiotherapy"}:
        return "/emr/patient-registry?system=modern"
    if specialty == "ayurveda":
        return "/emr/patient-registry?system=ayurveda"
    return "/emr/patient-registry"


def _consultation_url_for_doctor(doctor: Doctor, patient_id: int) -> str:
    specialty = (doctor.specialty or "ayurveda").strip().lower()
    if specialty in {"modern_medicine", "dental", "physiotherapy"}:
        return f"/emr/modern-consultation/{patient_id}"
    if specialty == "ayurveda":
        return f"/emr/ayurveda-consultation/{patient_id}"
    return f"/emr/integrated-consultation/{patient_id}"


def _seed_if_needed(db: Session) -> None:
    if db.query(EMRPatientProfile).count() == 0:
        seed_emr_from_existing_records(db)
        commit_with_retry(db)


def _doctor_role(doctor: Doctor) -> str:
    specialty = (doctor.specialty or "ayurveda").lower()
    return {
        "ayurveda": "Doctor - Ayurveda",
        "modern": "Doctor - Modern",
    }.get(specialty, "Doctor - Integrated")


def _base_context(request: Request, doctor: Doctor, active: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    context = {
        "request": request,
        "doctor": doctor,
        "user_name": doctor.full_name or doctor.username,
        "user_role": _doctor_role(doctor),
        "avatar_label": (doctor.full_name or doctor.username or "DR")[:2].upper(),
        "active_page": "profile",
        "nav_profile_href": "/emr/doctor-dashboard",
        "nav_consult_href": "/emr/clinical-decisions",
        "nav_appointments_href": "/appointments",
        "show_sidebar": True,
        "emr_active": active,
        "emr_section_links": SECTION_LINKS,
        "csrf_token": ensure_csrf_token(request),
        "flash": pop_flash(request),
        "help_terms": HELP_TERMS,
        "current_date": date.today(),
        "consultation_entry_href": _consultation_entry_url_for_doctor(doctor),
    }
    if extra:
        context.update(extra)
    return context


def _patient_for_doctor(db: Session, doctor_id: int, patient_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor_id).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _profile_for_patient(db: Session, patient: Patient) -> EMRPatientProfile:
    profile = db.query(EMRPatientProfile).filter(EMRPatientProfile.patient_id == patient.id).first()
    if profile is None:
        profile = ensure_emr_profile(db, patient)
        create_default_assessments(db, patient.id, patient.doctor_id)
        commit_with_retry(db)
    return profile


def _assessment_value(assessment_map: dict[str, Any], key: str, nested_key: str, fallback: str = "Pending") -> str:
    payload = assessment_map.get(key, {}) if isinstance(assessment_map, dict) else {}
    if isinstance(payload, dict):
        return str(payload.get(nested_key) or fallback)
    return fallback


def _diet_plan_text(plan: dict[str, Any]) -> str:
    sections: list[str] = []
    if plan.get("diagnosis_summary"):
        sections.append(f"Diagnosis Summary: {plan['diagnosis_summary']}")
    if plan.get("dosha_assessment"):
        sections.append(f"Dosha Assessment: {plan['dosha_assessment']}")
    for heading, key in [
        ("Meal Plan", "meal_plan"),
        ("Foods to Favor", "foods_to_favor"),
        ("Foods to Avoid", "foods_to_avoid"),
        ("Lifestyle Tips", "lifestyle_tips"),
        ("Precautions", "precautions"),
    ]:
        values = plan.get(key) or []
        if values:
            rendered = "\n".join(f"- {str(item).strip()}" for item in values if str(item).strip())
            if rendered:
                sections.append(f"{heading}:\n{rendered}")
    return "\n\n".join(sections).strip() or "Diet plan generated."


def _consultation_payload_to_model(consultation: EMRConsultation, payload: dict[str, Any]) -> None:
    for field in ["status", "title", "chief_complaint", "history_of_present_illness", "treatment_plan"]:
        if field in payload:
            setattr(consultation, field, str(payload[field]))
    if "notes" in payload:
        consultation.notes_json = payload["notes"]
    if "diagnoses" in payload:
        consultation.diagnosis_json = payload["diagnoses"]
    if payload.get("followup_date"):
        consultation.followup_date = datetime.strptime(payload["followup_date"], "%Y-%m-%d").date()


@router.get("/emr/doctor-dashboard")
def emr_doctor_dashboard(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(require_doctor_role)):
    _seed_if_needed(db)
    return render_template(templates, request,
        "emr/doctor_dashboard.html",
        _base_context(request, doctor, "doctor_dashboard", get_doctor_dashboard_data(db, doctor)),
    )


@router.get("/emr/patient-registry")
def emr_patient_registry(
    request: Request,
    q: str = Query(""),
    system: str = Query("all"),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(require_doctor_role),
):
    _seed_if_needed(db)
    query = db.query(Patient).filter(Patient.doctor_id == doctor.id)
    if q:
        query = query.filter(
            or_(
                Patient.name.ilike(f"%{q}%"),
                Patient.phone.ilike(f"%{q}%"),
                Patient.email.ilike(f"%{q}%"),
            )
        )
    patients = query.order_by(Patient.created_at.desc()).all()
    cards = []
    for patient in patients:
        profile = _profile_for_patient(db, patient)
        cards.append(
            {
                "patient": patient,
                "profile": profile,
                "prakriti": (profile.ayurveda_profile or {}).get("prakriti", "Not assessed"),
                "medical_flags": (profile.medical_history or {}).get("past_conditions", []),
            }
        )
    return render_template(templates, request,
        "emr/patient_registry.html",
        _base_context(request, doctor, "patient_registry", {"patient_cards": cards, "query": q, "system": system}),
    )


@router.get("/emr/patient-registration")
def emr_patient_registration_page(request: Request, doctor: Doctor = Depends(require_doctor_role)):
    return render_template(templates, request,
        "emr/patient_registration.html",
        _base_context(request, doctor, "patient_registration", {"ur_preview": f"UR-{date.today().year}-AUTO"}),
    )


@router.post("/emr/patient-registration")
def emr_patient_registration_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(""),
    gender: str = Form(...),
    age: int = Form(...),
    mobile: str = Form(...),
    email: str = Form(""),
    address: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_number: str = Form(""),
    consent_privacy: str = Form("false"),
    consent_telemedicine: str = Form("false"),
    prakriti_type: str = Form("Vata-Pitta"),
    agni_type: str = Form("Vishama"),
    medical_conditions: str = Form(""),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(require_doctor_role),
    _: None = Depends(verify_csrf),
):
    full_name = f"{first_name.strip()} {last_name.strip()}".strip()
    normalized_email = email.strip()
    existing_patient = None
    if normalized_email:
        existing_patient = (
            db.query(Patient)
            .filter(Patient.doctor_id == doctor.id, Patient.email == normalized_email)
            .first()
        )
    if existing_patient is None and mobile.strip():
        existing_patient = (
            db.query(Patient)
            .filter(Patient.doctor_id == doctor.id, Patient.phone == mobile.strip(), Patient.name == full_name)
            .first()
        )
    if existing_patient is not None:
        set_flash(request, f"{existing_patient.name} is already registered in your EMR. Opening the existing record instead.", "info")
        return RedirectResponse(url=f"/emr/patient/{existing_patient.id}", status_code=303)

    patient = Patient(
        doctor_id=doctor.id,
        name=full_name,
        age=age,
        gender=gender.strip(),
        phone=mobile.strip(),
        email=normalized_email,
        address=address.strip(),
    )
    db.add(patient)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing_patient = None
        if normalized_email:
            existing_patient = (
                db.query(Patient)
                .filter(Patient.doctor_id == doctor.id, Patient.email == normalized_email)
                .first()
            )
        if existing_patient is None and mobile.strip():
            existing_patient = (
                db.query(Patient)
                .filter(Patient.doctor_id == doctor.id, Patient.phone == mobile.strip(), Patient.name == full_name)
                .first()
            )
        if existing_patient is not None:
            set_flash(request, f"{existing_patient.name} is already registered in your EMR. Opening the existing record instead.", "info")
            return RedirectResponse(url=f"/emr/patient/{existing_patient.id}", status_code=303)
        set_flash(request, "This patient could not be registered because of a data conflict.", "danger")
        return RedirectResponse(url="/emr/patient-registration", status_code=303)
    profile = EMRPatientProfile(
        patient_id=patient.id,
        ur_number=generate_ur_number(patient.id),
        profile_data={
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "mobile": mobile.strip(),
            "email": email.strip(),
            "address": address.strip(),
            "gender": gender.strip(),
            "age": age,
        },
        medical_history={"past_conditions": [item.strip() for item in medical_conditions.split(",") if item.strip()]},
        ayurveda_profile={"prakriti": prakriti_type.strip(), "agni": agni_type.strip(), "vikriti": "Pending assessment"},
        emergency_contact={"name": emergency_contact_name.strip(), "phone": emergency_contact_number.strip()},
        consent_flags={
            "privacy": consent_privacy.lower() == "true",
            "telemedicine": consent_telemedicine.lower() == "true",
        },
    )
    db.add(profile)
    create_default_assessments(db, patient.id, doctor.id)
    write_emr_audit_log(
        db,
        doctor.id,
        "patient_registered",
        "patient",
        patient.id,
        patient.id,
        {"ur_number": profile.ur_number},
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    commit_with_retry(db)
    set_flash(request, f"EMR profile created for {patient.name}.", "success")
    return RedirectResponse(url=f"/emr/patient/{patient.id}", status_code=303)


@router.get("/emr/patient/{patient_id}")
def emr_patient_detail(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(require_doctor_role)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    consultations = db.query(EMRConsultation).filter(EMRConsultation.patient_id == patient.id).order_by(EMRConsultation.created_at.desc()).all()
    assessments = db.query(EMRAssessment).filter(EMRAssessment.patient_id == patient.id).all()
    prescriptions = db.query(EMRPrescription).filter(EMRPrescription.patient_id == patient.id).order_by(EMRPrescription.created_at.desc()).all()
    vitals = db.query(EMRVital).filter(EMRVital.patient_id == patient.id).order_by(EMRVital.recorded_at.desc()).limit(10).all()
    timeline = build_patient_timeline(db, patient.id)
    assessment_map = {assessment.assessment_type: assessment.payload for assessment in assessments}
    return render_template(templates, request,
        "emr/patient_detail.html",
        _base_context(
            request,
            doctor,
            "patient_detail",
            {
                "patient_record": serialize_patient(patient, profile),
                "patient": patient,
                "profile": profile,
                "consultations": consultations,
                "assessments": assessment_map,
                "prescriptions": prescriptions,
                "vitals": vitals,
                "timeline": timeline,
                "current_doctor_type": normalize_doctor_type(request.session.get("portal_doctor_type"), doctor.specialty),
                "consultation_href": _consultation_url_for_doctor(doctor, patient.id),
            },
        ),
    )


@router.post("/api/ai/diet-plan/{patient_id}")
async def generate_patient_diet_plan(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(require_doctor_role),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    consultations = (
        db.query(EMRConsultation)
        .filter(EMRConsultation.patient_id == patient.id)
        .order_by(EMRConsultation.created_at.desc())
        .all()
    )
    assessments = db.query(EMRAssessment).filter(EMRAssessment.patient_id == patient.id).all()
    assessment_map = {assessment.assessment_type: assessment.payload for assessment in assessments}
    latest_consultation = consultations[0] if consultations else None
    patient_data = {
        "patient_name": patient.name,
        "diagnosis": getattr(latest_consultation, "title", "") or "Ayurveda follow-up",
        "symptoms": getattr(latest_consultation, "chief_complaint", "") or "",
        "notes": getattr(latest_consultation, "treatment_plan", "") or getattr(latest_consultation, "history_of_present_illness", "") or "",
        "prakriti": _assessment_value(assessment_map, "prakriti", "label", (profile.ayurveda_profile or {}).get("prakriti", "Pending")),
        "vikriti": _assessment_value(assessment_map, "vikriti", "label", (profile.ayurveda_profile or {}).get("vikriti", "Pending")),
        "agni": _assessment_value(assessment_map, "agni", "type", (profile.ayurveda_profile or {}).get("agni", "Pending")),
    }
    plan = await generate_diet_plan(patient_data)
    diet_plan = _diet_plan_text(plan)
    write_emr_audit_log(
        db,
        doctor.id,
        "ai_diet_plan_generated",
        "patient",
        patient.id,
        patient.id,
        {"patient_name": patient.name},
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    commit_with_retry(db)
    return JSONResponse({"success": True, "diet_plan": diet_plan, "structured_plan": plan})


@router.post("/api/ai/diet-plan/{patient_id}/save")
def save_patient_diet_plan(
    patient_id: int,
    request: Request,
    payload: dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(require_doctor_role),
):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    diet_plan = str(payload.get("diet_plan", "")).strip()
    if not diet_plan:
        return JSONResponse({"success": False, "error": "Diet plan is required."}, status_code=400)
    ayurveda_profile = dict(profile.ayurveda_profile or {})
    ayurveda_profile["latest_ai_diet_plan"] = diet_plan
    profile.ayurveda_profile = ayurveda_profile
    write_emr_audit_log(
        db,
        doctor.id,
        "ai_diet_plan_saved",
        "patient",
        patient.id,
        patient.id,
        {"saved_length": len(diet_plan)},
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    commit_with_retry(db)
    return JSONResponse({"success": True})


@router.get("/emr/modern-consultation/new")
def emr_modern_consultation_entry(request: Request, doctor: Doctor = Depends(require_doctor_role)):
    set_flash(request, "Choose a patient before starting a modern consultation.", "info")
    return RedirectResponse(url="/emr/patient-registry?system=modern", status_code=303)


@router.get("/emr/consultation/new")
def emr_consultation_entry(doctor: Doctor = Depends(require_doctor_role)):
    return RedirectResponse(url=_consultation_entry_url_for_doctor(doctor), status_code=303)


@router.get("/emr/consultation/{patient_id}")
def emr_consultation_router(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(require_doctor_role)):
    _patient_for_doctor(db, doctor.id, patient_id)
    return RedirectResponse(url=_consultation_url_for_doctor(doctor, patient_id), status_code=303)


@router.get("/emr/modern-consultation/{patient_id}")
def emr_modern_consultation(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(require_modern_doctor)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    recent_vitals = db.query(EMRVital).filter(EMRVital.patient_id == patient.id).order_by(EMRVital.recorded_at.desc()).limit(5).all()
    return render_template(templates, request,
        "emr/modern_consultation.html",
        _base_context(request, doctor, "modern_consultation", {"patient": patient, "profile": profile, "recent_vitals": recent_vitals, "icd_codes": ICD11_SAMPLE_CODES, "drug_library": MODERN_DRUG_LIBRARY}),
    )


@router.get("/emr/ayurveda-consultation/new")
def emr_ayurveda_consultation_entry(request: Request, doctor: Doctor = Depends(require_doctor_role)):
    set_flash(request, "Choose a patient before starting an Ayurveda consultation.", "info")
    return RedirectResponse(url="/emr/patient-registry?system=ayurveda", status_code=303)


@router.get("/emr/ayurveda-consultation/{patient_id}")
def emr_ayurveda_consultation(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(require_ayurveda_doctor)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    assessments = db.query(EMRAssessment).filter(EMRAssessment.patient_id == patient.id).all()
    assessment_map = {item.assessment_type: item.payload for item in assessments}
    return render_template(templates, request,
        "emr/ayurveda_consultation.html",
        _base_context(request, doctor, "ayurveda_consultation", {"patient": patient, "profile": profile, "assessments": assessment_map, "prakriti_questions": PRAKRITI_QUESTION_BANK[:18], "formulations": AYURVEDA_FORMULATION_LIBRARY}),
    )


@router.get("/emr/integrated-consultation/{patient_id}")
def emr_integrated_consultation(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(require_integrated_access)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    return render_template(templates, request,
        "emr/integrated_consultation.html",
        _base_context(request, doctor, "integrated_consultation", {"patient": patient, "profile": profile, "interaction_pairs": DRUG_HERB_INTERACTIONS}),
    )


@router.get("/emr/prescription-viewer")
def emr_prescription_viewer(request: Request, patient_id: int | None = Query(None), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    query = db.query(EMRPrescription).filter(EMRPrescription.doctor_id == doctor.id)
    if patient_id:
        query = query.filter(EMRPrescription.patient_id == patient_id)
    prescriptions = query.order_by(EMRPrescription.created_at.desc()).all()
    return render_template(templates, request,
        "emr/prescription_viewer.html",
        _base_context(request, doctor, "prescription_viewer", {"prescriptions": prescriptions, "selected_patient_id": patient_id}),
    )


@router.get("/emr/lab-dashboard")
def emr_lab_dashboard(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _seed_if_needed(db)
    orders = db.query(EMRLabOrder).filter(EMRLabOrder.doctor_id == doctor.id).order_by(EMRLabOrder.ordered_at.desc()).all()
    return render_template(templates, request,
        "emr/lab_dashboard.html",
        {"request": request, **_base_context(request, doctor, "lab_dashboard", {"lab_orders": orders})},
    )


@router.get("/emr/vital-tracker")
def emr_vital_tracker(request: Request, patient_id: int | None = Query(None), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _seed_if_needed(db)
    vitals = db.query(EMRVital).filter(EMRVital.doctor_id == doctor.id)
    if patient_id:
        vitals = vitals.filter(EMRVital.patient_id == patient_id)
    vital_rows = vitals.order_by(EMRVital.recorded_at.desc()).limit(30).all()
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).order_by(Patient.name.asc()).all()
    return render_template(templates, request,
        "emr/vital_tracker.html",
        {"request": request, **_base_context(request, doctor, "vital_tracker", {"vitals": vital_rows, "patients": patients, "selected_patient_id": patient_id})},
    )


@router.get("/emr/clinical-decisions")
def emr_clinical_decisions(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _seed_if_needed(db)
    return render_template(templates, request,
        "emr/clinical_decisions.html",
        {"request": request, **_base_context(request, doctor, "clinical_decisions", {"interaction_pairs": DRUG_HERB_INTERACTIONS, "icd_codes": ICD11_SAMPLE_CODES})},
    )


@router.get("/emr/panchakarma-scheduler")
def emr_panchakarma_scheduler(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).limit(8).all()
    plans = [{"name": "Virechana Preparation", "patient": patient.name, "staff": "Therapy Team A", "status": "Scheduled", "date": date.today().isoformat()} for patient in patients[:3]]
    return render_template(templates, request,
        "emr/panchakarma_scheduler.html",
        {"request": request, **_base_context(request, doctor, "panchakarma_scheduler", {"plans": plans})},
    )


@router.get("/emr/clinical-reporting")
def emr_clinical_reporting(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    return render_template(templates, request,
        "emr/clinical_reporting.html",
        _base_context(
            request,
            doctor,
            "clinical_reporting",
            {
                "dashboard_data": get_doctor_dashboard_data(db, doctor),
                "dosha_distribution": get_dosha_distribution(db, doctor.id),
                "revenue_trend": get_revenue_trend(db, doctor.id, days=10),
            },
        ),
    )


@router.get("/emr/telemedicine")
def emr_telemedicine(request: Request, doctor: Doctor = Depends(get_current_doctor)):
    return render_template(templates, request,
        "emr/telemedicine.html",
        {"request": request, **_base_context(request, doctor, "telemedicine", {})},
    )


@router.get("/emr/patient-portal/{patient_id}")
def emr_patient_portal(patient_id: int, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    prescriptions = db.query(EMRPrescription).filter(EMRPrescription.patient_id == patient.id).order_by(EMRPrescription.created_at.desc()).all()
    labs = db.query(EMRLabOrder).filter(EMRLabOrder.patient_id == patient.id).order_by(EMRLabOrder.ordered_at.desc()).all()
    appointments = db.query(Appointment).filter(Appointment.patient_id == patient.id).order_by(Appointment.date.desc()).all()
    return render_template(templates, request,
        "emr/patient_portal.html",
        {"request": request, **_base_context(request, doctor, "patient_portal", {"patient": patient, "profile": profile, "prescriptions": prescriptions, "labs": labs, "appointments": appointments})},
    )


@router.get("/emr/consent-forms")
def emr_consent_forms(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    forms = db.query(EMRConsentForm).filter(EMRConsentForm.doctor_id == doctor.id).order_by(EMRConsentForm.created_at.desc()).all()
    return render_template(templates, request,
        "emr/consent_forms.html",
        {"request": request, **_base_context(request, doctor, "consent_forms", {"forms": forms})},
    )


@router.get("/emr/audit-trail")
def emr_audit_trail(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    audit_logs = db.query(EMRAuditLog).filter(EMRAuditLog.user_id == doctor.id).order_by(EMRAuditLog.created_at.desc()).limit(50).all()
    return render_template(templates, request,
        "emr/audit_trail.html",
        {"request": request, **_base_context(request, doctor, "audit_trail", {"audit_logs": audit_logs})},
    )


@router.get("/emr/data-quality")
def emr_data_quality(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    return render_template(templates, request,
        "emr/data_quality.html",
        {"request": request, **_base_context(request, doctor, "data_quality", get_data_quality_report(db, doctor.id))},
    )


@router.get("/emr/billing-integration")
def emr_billing_integration(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    return render_template(templates, request,
        "emr/billing_integration.html",
        {"request": request, **_base_context(request, doctor, "billing_integration", {"revenue_trend": get_revenue_trend(db, doctor.id, days=14)})},
    )


@router.get("/emr/mobile-emr")
def emr_mobile_emr(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    recent_patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).order_by(Patient.created_at.desc()).limit(6).all()
    return render_template(templates, request,
        "emr/mobile_emr.html",
        _base_context(
            request,
            doctor,
            "mobile_emr",
            {
                "recent_patients": recent_patients,
                "consultation_links": {patient.id: _consultation_url_for_doctor(doctor, patient.id) for patient in recent_patients},
            },
        ),
    )


@router.get("/emr/test-emr")
def emr_test_page(request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).limit(5).all()
    return render_template(templates, request,
        "emr/test_emr.html",
        {"request": request, **_base_context(request, doctor, "test_emr", {"patients": patients, "question_count": len(PRAKRITI_QUESTION_BANK)})},
    )


@router.get("/emr/test-emr/{action}")
def emr_test_redirect(action: str, request: Request, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    normalized_action = action.strip().lower()
    if normalized_action == "registration":
        return RedirectResponse(url="/emr/patient-registration", status_code=303)

    patient = (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor.id)
        .order_by(Patient.created_at.desc())
        .first()
    )
    if patient is None:
        set_flash(request, "Add a patient first before testing consultation workflows.", "info")
        return RedirectResponse(url="/emr/patient-registration", status_code=303)

    specialty = (doctor.specialty or "ayurveda").strip().lower()
    modern_specialties = {"modern_medicine", "dental", "physiotherapy"}

    if normalized_action == "soap":
        if specialty in modern_specialties:
            return RedirectResponse(url=f"/emr/modern-consultation/{patient.id}", status_code=303)
        set_flash(request, "SOAP note testing is optimized for modern specialties. Opening integrated consultation for this doctor.", "info")
        return RedirectResponse(url=f"/emr/integrated-consultation/{patient.id}", status_code=303)

    if normalized_action == "prakriti":
        if specialty == "ayurveda":
            return RedirectResponse(url=f"/emr/ayurveda-consultation/{patient.id}", status_code=303)
        set_flash(request, "Prakriti assessment is optimized for Ayurveda doctors. Opening integrated consultation for this doctor.", "info")
        return RedirectResponse(url=f"/emr/integrated-consultation/{patient.id}", status_code=303)

    raise HTTPException(status_code=404, detail="Unknown EMR test action.")


@router.get("/api/patients/search")
def api_patient_search(q: str = Query(""), system: str = Query("all"), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    query = db.query(Patient).filter(Patient.doctor_id == doctor.id)
    if q:
        query = query.filter(or_(Patient.name.ilike(f"%{q}%"), Patient.phone.ilike(f"%{q}%"), Patient.email.ilike(f"%{q}%")))
    patients = query.order_by(Patient.created_at.desc()).limit(50).all()
    return {"success": True, "count": len(patients), "results": [{**serialize_patient(item, _profile_for_patient(db, item)), "system": system} for item in patients]}


@router.post("/api/patients/register")
def api_patient_register(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    full_name = f"{first_name} {last_name}".strip() or str(payload.get("name", "")).strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Patient name is required")
    patient = Patient(
        doctor_id=doctor.id,
        name=full_name,
        age=int(payload.get("age", 0) or 0),
        gender=str(payload.get("gender", "other")),
        phone=str(payload.get("mobile", payload.get("phone", ""))),
        email=str(payload.get("email", "")),
        address=str(payload.get("address", "")),
    )
    db.add(patient)
    db.flush()
    profile = EMRPatientProfile(
        patient_id=patient.id,
        ur_number=generate_ur_number(patient.id),
        profile_data=payload,
        medical_history=payload.get("medical_history", {}),
        ayurveda_profile=payload.get("ayurveda_profile", {}),
        allergies=payload.get("allergies", []),
        family_history=payload.get("family_history", []),
        emergency_contact=payload.get("emergency_contact", {}),
        consent_flags=payload.get("consent", {}),
    )
    db.add(profile)
    write_emr_audit_log(db, doctor.id, "api_patient_registered", "patient", patient.id, patient.id, {"source": "api"})
    commit_with_retry(db)
    return {"success": True, "patient": serialize_patient(patient, profile)}


@router.get("/api/patients/{patient_id}")
def api_patient_detail(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    return {"success": True, "patient": serialize_patient(patient, _profile_for_patient(db, patient))}


@router.put("/api/patients/{patient_id}")
def api_patient_update(patient_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, patient_id)
    profile = _profile_for_patient(db, patient)
    patient.name = str(payload.get("name", patient.name)).strip() or patient.name
    patient.phone = str(payload.get("phone", patient.phone)).strip()
    patient.email = str(payload.get("email", patient.email)).strip()
    patient.address = str(payload.get("address", patient.address)).strip()
    profile.profile_data = {**(profile.profile_data or {}), **payload.get("profile", {})}
    profile.medical_history = payload.get("medical_history", profile.medical_history)
    profile.ayurveda_profile = payload.get("ayurveda_profile", profile.ayurveda_profile)
    write_emr_audit_log(db, doctor.id, "patient_updated", "patient", patient.id, patient.id, {"updated_fields": list(payload.keys())})
    commit_with_retry(db)
    return {"success": True, "patient": serialize_patient(patient, profile)}


@router.get("/api/patients/{patient_id}/timeline")
def api_patient_timeline(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _patient_for_doctor(db, doctor.id, patient_id)
    return {"success": True, "timeline": build_patient_timeline(db, patient_id)}


@router.post("/api/consultations/{system_type}")
def api_create_consultation(system_type: str, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    if system_type not in {"modern", "ayurveda", "integrated"}:
        raise HTTPException(status_code=404, detail="Unsupported consultation type")
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    consultation = EMRConsultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_id=payload.get("appointment_id"),
        system_type=system_type,
        status=str(payload.get("status", "draft")),
        title=str(payload.get("title", f"{system_type.title()} consultation")),
        chief_complaint=str(payload.get("chief_complaint", "")),
        history_of_present_illness=str(payload.get("history_of_present_illness", "")),
        notes_json=payload.get("notes", {}),
        diagnosis_json=payload.get("diagnoses", []),
        treatment_plan=str(payload.get("treatment_plan", "")),
        followup_date=datetime.strptime(payload["followup_date"], "%Y-%m-%d").date() if payload.get("followup_date") else None,
    )
    db.add(consultation)
    db.flush()
    if payload.get("vitals"):
        db.add(EMRVital(patient_id=patient.id, doctor_id=doctor.id, consultation_id=consultation.id, payload=payload["vitals"], notes=str(payload.get("vital_notes", ""))))
    for assessment_type, assessment_payload in (payload.get("assessments", {}) or {}).items():
        db.add(EMRAssessment(patient_id=patient.id, doctor_id=doctor.id, consultation_id=consultation.id, assessment_type=assessment_type, payload=assessment_payload))
    if payload.get("prescription_items"):
        db.add(EMRPrescription(consultation_id=consultation.id, patient_id=patient.id, doctor_id=doctor.id, system_type=system_type, notes=str(payload.get("prescription_notes", "")), items_json=payload.get("prescription_items", [])))
    write_emr_audit_log(db, doctor.id, "consultation_created", "consultation", consultation.id, patient.id, {"system_type": system_type})
    commit_with_retry(db)
    return {"success": True, "consultation": serialize_consultation(consultation)}


@router.get("/api/consultations/{consultation_id:int}")
def api_consultation_detail(consultation_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    consultation = db.query(EMRConsultation).filter(EMRConsultation.id == consultation_id, EMRConsultation.doctor_id == doctor.id).first()
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return {"success": True, "consultation": serialize_consultation(consultation)}


@router.put("/api/consultations/{consultation_id:int}")
def api_consultation_update(consultation_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    consultation = db.query(EMRConsultation).filter(EMRConsultation.id == consultation_id, EMRConsultation.doctor_id == doctor.id).first()
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    _consultation_payload_to_model(consultation, payload)
    write_emr_audit_log(db, doctor.id, "consultation_updated", "consultation", consultation.id, consultation.patient_id, {"updated_fields": list(payload.keys())})
    commit_with_retry(db)
    return {"success": True, "consultation": serialize_consultation(consultation)}


@router.get("/api/consultations/patient/{patient_id}")
def api_consultations_for_patient(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _patient_for_doctor(db, doctor.id, patient_id)
    consultations = db.query(EMRConsultation).filter(EMRConsultation.patient_id == patient_id, EMRConsultation.doctor_id == doctor.id).order_by(EMRConsultation.created_at.desc()).all()
    return {"success": True, "consultations": [serialize_consultation(item) for item in consultations]}


@router.post("/api/prescriptions/{system_type}")
def api_create_prescription(system_type: str, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    if system_type not in {"modern", "ayurveda"}:
        raise HTTPException(status_code=404, detail="Unsupported prescription type")
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    prescription = EMRPrescription(
        consultation_id=payload.get("consultation_id"),
        patient_id=patient.id,
        doctor_id=doctor.id,
        system_type=system_type,
        status=str(payload.get("status", "active")),
        notes=str(payload.get("notes", "")),
        items_json=payload.get("items", []),
    )
    db.add(prescription)
    commit_with_retry(db)
    return {"success": True, "prescription": serialize_prescription(prescription)}


@router.get("/api/prescriptions/{prescription_id:int}")
def api_prescription_detail(prescription_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    prescription = db.query(EMRPrescription).filter(EMRPrescription.id == prescription_id, EMRPrescription.doctor_id == doctor.id).first()
    if prescription is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return {"success": True, "prescription": serialize_prescription(prescription)}


@router.get("/api/prescriptions/patient/{patient_id}/active")
def api_active_prescriptions(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _patient_for_doctor(db, doctor.id, patient_id)
    prescriptions = db.query(EMRPrescription).filter(EMRPrescription.patient_id == patient_id, EMRPrescription.status == "active").order_by(EMRPrescription.created_at.desc()).all()
    return {"success": True, "prescriptions": [serialize_prescription(item) for item in prescriptions]}


@router.post("/api/prescriptions/{prescription_id:int}/refill")
def api_refill_prescription(prescription_id: int, payload: dict[str, Any] = Body(default={}), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    prescription = db.query(EMRPrescription).filter(EMRPrescription.id == prescription_id, EMRPrescription.doctor_id == doctor.id).first()
    if prescription is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    prescription.refill_count += int(payload.get("count", 1) or 1)
    commit_with_retry(db)
    return {"success": True, "prescription": serialize_prescription(prescription)}


@router.post("/api/labs/order")
def api_lab_order(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    order = EMRLabOrder(
        patient_id=patient.id,
        doctor_id=doctor.id,
        consultation_id=payload.get("consultation_id"),
        lab_name=str(payload.get("lab_name", "Integrated Diagnostics")),
        priority=str(payload.get("priority", "routine")),
        status=str(payload.get("status", "pending")),
        tests_json=payload.get("tests", []),
        results_json=payload.get("results", []),
    )
    db.add(order)
    commit_with_retry(db)
    return {"success": True, "lab_order": serialize_lab_order(order)}


@router.put("/api/labs/result/{test_id}")
def api_lab_result_update(test_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    order = db.query(EMRLabOrder).filter(EMRLabOrder.id == test_id, EMRLabOrder.doctor_id == doctor.id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Lab order not found")
    order.results_json = payload.get("results", order.results_json)
    order.status = str(payload.get("status", "completed"))
    order.completed_at = datetime.now()
    commit_with_retry(db)
    return {"success": True, "lab_order": serialize_lab_order(order)}


@router.get("/api/labs/patient/{patient_id}")
def api_labs_for_patient(patient_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    _patient_for_doctor(db, doctor.id, patient_id)
    orders = db.query(EMRLabOrder).filter(EMRLabOrder.patient_id == patient_id).order_by(EMRLabOrder.ordered_at.desc()).all()
    return {"success": True, "lab_orders": [serialize_lab_order(order) for order in orders]}


@router.post("/api/ayurveda/prakriti/assess")
def api_prakriti_assess(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    assessment = EMRAssessment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        consultation_id=payload.get("consultation_id"),
        assessment_type="prakriti",
        payload={**calculate_prakriti(list(payload.get("answers", []))), "label": payload.get("label", "Calculated prakriti")},
    )
    db.add(assessment)
    commit_with_retry(db)
    return {"success": True, "assessment": assessment.payload}


@router.post("/api/ayurveda/srotas/examine")
def api_srotas_examine(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    assessment = EMRAssessment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        consultation_id=payload.get("consultation_id"),
        assessment_type="srotas",
        payload=payload.get("srotas", {}),
    )
    db.add(assessment)
    commit_with_retry(db)
    return {"success": True, "assessment": assessment.payload}


@router.get("/api/interactions/check")
def api_check_interactions(drugs: list[str] = Query(default=[]), herbs: list[str] = Query(default=[]), doctor: Doctor = Depends(get_current_doctor)):
    findings = []
    for drug in drugs:
        matches = [herb for herb in herbs if herb in DRUG_HERB_INTERACTIONS.get(drug, [])]
        if matches:
            findings.append({"drug": drug, "herbs": matches, "severity": "moderate", "recommendation": "Review integrated dosing and timing."})
    return {"success": True, "doctor_id": doctor.id, "findings": findings}


@router.get("/api/icd11/search")
def api_icd11_search(q: str = Query(""), doctor: Doctor = Depends(get_current_doctor)):
    needle = q.lower().strip()
    results = [item for item in ICD11_SAMPLE_CODES if not needle or needle in item["code"].lower() or needle in item["diagnosis"].lower()]
    return {"success": True, "doctor_id": doctor.id, "results": results[:20]}


@router.post("/api/analytics/outcomes")
def api_analytics_outcomes(payload: dict[str, Any] = Body(default={}), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    outcomes = db.query(EMROutcome).join(Patient, Patient.id == EMROutcome.patient_id).filter(Patient.doctor_id == doctor.id).all()
    if payload.get("patient_id"):
        outcomes = [item for item in outcomes if item.patient_id == int(payload["patient_id"])]
    average = round(sum(item.improvement_percentage for item in outcomes) / len(outcomes), 2) if outcomes else 0
    return {"success": True, "count": len(outcomes), "average_improvement": average, "ratings": [item.rating for item in outcomes]}


@router.get("/api/reports/clinical")
def api_clinical_report(from_date: str | None = Query(None, alias="from"), to_date: str | None = Query(None, alias="to"), doctor_id: int | None = Query(None, alias="doctor"), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    target_doctor_id = doctor_id or doctor.id
    query = db.query(EMRConsultation).filter(EMRConsultation.doctor_id == target_doctor_id)
    if from_date:
        query = query.filter(EMRConsultation.created_at >= datetime.fromisoformat(from_date))
    if to_date:
        query = query.filter(EMRConsultation.created_at <= datetime.fromisoformat(to_date))
    consultations = query.order_by(EMRConsultation.created_at.desc()).all()
    return {"success": True, "count": len(consultations), "consultations": [serialize_consultation(item) for item in consultations]}


@router.get("/api/reports/ayurveda/dosha_distribution")
def api_dosha_distribution(db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    return {"success": True, "distribution": get_dosha_distribution(db, doctor.id)}


@router.get("/api/reports/financial/daily")
def api_financial_daily(db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    return {"success": True, "trend": get_revenue_trend(db, doctor.id, days=14)}


@router.get("/api/audit/logs")
def api_audit_logs(patient: int | None = Query(None), doctor_id: int | None = Query(None, alias="doctor"), action: str | None = Query(None), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    query = db.query(EMRAuditLog).filter(EMRAuditLog.user_id == (doctor_id or doctor.id))
    if patient:
        query = query.filter(EMRAuditLog.patient_id == patient)
    if action:
        query = query.filter(EMRAuditLog.action == action)
    logs = query.order_by(EMRAuditLog.created_at.desc()).limit(100).all()
    return {"success": True, "logs": [{"id": log.id, "action": log.action, "record_type": log.record_type, "record_id": log.record_id, "patient_id": log.patient_id, "created_at": log.created_at.isoformat() if log.created_at else None} for log in logs]}


@router.post("/api/audit/log")
def api_audit_log(payload: dict[str, Any] = Body(...), request: Request = None, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    log = write_emr_audit_log(
        db,
        doctor.id,
        str(payload.get("action", "view")),
        str(payload.get("record_type", "generic")),
        payload.get("record_id"),
        payload.get("patient_id"),
        payload,
        request.client.host if request and request.client else "",
        request.headers.get("user-agent", "") if request else "",
    )
    commit_with_retry(db)
    return {"success": True, "log_id": log.id}


@router.get("/api/appointments/doctor/{doctor_id}/today")
def api_today_appointments(doctor_id: int, db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    target = doctor.id if doctor_id != doctor.id else doctor_id
    appointments = db.query(Appointment).join(Patient, Patient.id == Appointment.patient_id).filter(Patient.doctor_id == target, Appointment.date == date.today()).order_by(Appointment.time.asc()).all()
    return {"success": True, "appointments": [{"id": item.id, "patient_id": item.patient_id, "patient_name": item.patient.name if item.patient else "", "date": item.date.isoformat() if item.date else None, "time": item.time, "reason": item.reason, "status": item.status} for item in appointments]}


@router.post("/api/appointments/book")
def api_book_appointment(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patient = _patient_for_doctor(db, doctor.id, int(payload.get("patient_id")))
    appointment = Appointment(
        patient_id=patient.id,
        date=datetime.strptime(str(payload.get("appointment_date")), "%Y-%m-%d").date(),
        time=str(payload.get("appointment_time", "09:00")),
        reason=str(payload.get("reason", "Consultation")),
        status=str(payload.get("status", "scheduled")),
    )
    db.add(appointment)
    commit_with_retry(db)
    return {"success": True, "appointment_id": appointment.id}


@router.put("/api/appointments/{appointment_id}/status")
def api_update_appointment_status(appointment_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    appointment = db.query(Appointment).join(Patient, Patient.id == Appointment.patient_id).filter(Appointment.id == appointment_id, Patient.doctor_id == doctor.id).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment.status = str(payload.get("status", appointment.status))
    commit_with_retry(db)
    return {"success": True, "appointment_id": appointment.id, "status": appointment.status}


@router.get("/emr/export/patients")
def export_patients_csv(db: Session = Depends(get_db), doctor: Doctor = Depends(get_current_doctor)):
    patients = db.query(Patient).filter(Patient.doctor_id == doctor.id).all()
    rows = ["ur_number,name,phone,email,gender,age"]
    for patient in patients:
        profile = db.query(EMRPatientProfile).filter(EMRPatientProfile.patient_id == patient.id).first()
        rows.append(f'{profile.ur_number if profile else ""},{patient.name},{patient.phone},{patient.email},{patient.gender},{patient.age}')
    return JSONResponse({"success": True, "csv": "\n".join(rows)})
