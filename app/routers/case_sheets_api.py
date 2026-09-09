from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import commit_with_retry, get_db
from app.models import Appointment, CaseSheet, Doctor, Patient
from models.medicine import Medicine
from models.prescription import Prescription
from services.ai_provider import call_gemini

logger = logging.getLogger("case_sheets_api")

router = APIRouter(prefix="/api", tags=["Prescriptions & Case Sheets"])


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class MedicineItem(BaseModel):
    medicine_name: str
    dosage: Optional[str] = "1 unit"
    frequency: Optional[str] = "1-0-1"
    duration: Optional[str] = "5 days"
    instructions: Optional[str] = "After meals"
    confidence: Optional[float] = None


class SavePrescriptionRequest(BaseModel):
    patient_id: Optional[int] = None
    patient_name: str
    patient_age: Optional[int] = 35
    patient_gender: Optional[str] = "Other"
    diagnosis: Optional[str] = "Ayurvedic Consultation"
    symptoms: Optional[str] = ""
    advice: Optional[str] = ""
    medicines: List[MedicineItem] = []
    doctor_id: Optional[int] = 1


class CopilotChatRequest(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    message: str
    history: Optional[List[dict[str, str]]] = Field(default_factory=list)


def format_frequency_label(freq: str) -> str:
    cleaned = str(freq or "").strip()
    patterns = {
        "1-0-1": "1-0-1 [Morning: 1, Afternoon: 0, Night: 1] (Twice daily)",
        "1-1-1": "1-1-1 [Morning: 1, Afternoon: 1, Night: 1] (Three times daily)",
        "1-0-0": "1-0-0 [Morning: 1, Afternoon: 0, Night: 0] (Once daily - Morning)",
        "0-0-1": "0-0-1 [Morning: 0, Afternoon: 0, Night: 1] (Once daily - Night)",
        "0-1-0": "0-1-0 [Morning: 0, Afternoon: 1, Night: 0] (Once daily - Afternoon)",
        "1-1-0": "1-1-0 [Morning: 1, Afternoon: 1, Night: 0] (Twice daily - Morning & Afternoon)",
        "0-1-1": "0-1-1 [Morning: 0, Afternoon: 1, Night: 1] (Twice daily - Afternoon & Night)",
        "BD": "1-0-1 [Morning: 1, Afternoon: 0, Night: 1] (Twice daily)",
        "BID": "1-0-1 [Morning: 1, Afternoon: 0, Night: 1] (Twice daily)",
        "TDS": "1-1-1 [Morning: 1, Afternoon: 1, Night: 1] (Three times daily)",
        "TID": "1-1-1 [Morning: 1, Afternoon: 1, Night: 1] (Three times daily)",
        "OD": "1-0-0 [Morning: 1, Afternoon: 0, Night: 0] (Once daily)",
        "HS": "0-0-1 [Morning: 0, Afternoon: 0, Night: 1] (Bedtime / Night)",
    }
    return patterns.get(cleaned.upper(), cleaned or "1-0-1 [Morning: 1, Afternoon: 0, Night: 1]")


# ==========================================
# PRESCRIPTION & CASE SHEET ENDPOINTS
# ==========================================

@router.post("/prescriptions/save")
def save_prescription_and_case(
    payload: SavePrescriptionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Save an OCR-decoded or manually created prescription into the database,
    linking or creating the Patient and generating a corresponding Case Sheet.
    """
    try:
        doctor_id = payload.doctor_id or 1
        # Ensure a default doctor exists
        doctor = db.get(Doctor, doctor_id)
        if not doctor:
            doctor = db.query(Doctor).first()
            if doctor:
                doctor_id = doctor.id

        patient: Optional[Patient] = None
        # 1. Look up patient by ID if provided
        if payload.patient_id and payload.patient_id > 0:
            patient = db.get(Patient, payload.patient_id)

        # 2. If not found by ID, look up by name
        if not patient and payload.patient_name.strip():
            patient = (
                db.query(Patient)
                .filter(Patient.name.ilike(payload.patient_name.strip()))
                .first()
            )

        # 3. If patient still doesn't exist, create a new Patient record
        if not patient:
            clean_name = payload.patient_name.strip() or "New Patient"
            patient = Patient(
                doctor_id=doctor_id,
                name=clean_name,
                age=payload.patient_age or 35,
                gender=payload.patient_gender or "Other",
                phone="",
                email=f"{clean_name.lower().replace(' ', '')}{int(datetime.now().timestamp())}@kash.clinic",
                address="Consultation Record",
            )
            db.add(patient)
            db.flush()

        # Convert medicines to dict list
        medicines_data = [m.model_dump() for m in payload.medicines]

        # 4. Save Prescription
        rx = Prescription(
            patient_id=patient.id,
            doctor_id=doctor_id,
            diagnosis=payload.diagnosis or "Ayurvedic Consultation",
            medicines=medicines_data,
            advice=payload.advice or "Follow prescribed dosage with warm water.",
            follow_up_days=14,
            ai_accepted=True,
            ai_feedback=f"OCR decoded {len(medicines_data)} medicines",
        )
        db.add(rx)
        db.flush()

        # 5. Format medicines for CaseSheet with clear 3-times timing explanation
        med_lines = []
        for m in medicines_data:
            freq_raw = m.get('frequency', '1-0-1')
            freq_explained = format_frequency_label(freq_raw)
            line = f"• {m.get('medicine_name')}: {m.get('dosage', '1 unit')} | Schedule: {freq_explained} | Duration: {m.get('duration', '7 days')}"
            if m.get('instructions'):
                line += f" ({m.get('instructions')})"
            med_lines.append(line)
        med_formatted_text = "\n".join(med_lines)

        # 6. Save Case Sheet
        case_notes = payload.advice or ""
        if payload.symptoms:
            symptoms_text = payload.symptoms
        else:
            symptoms_text = f"Prescription recorded with {len(medicines_data)} medicines"

        case = CaseSheet(
            patient_id=patient.id,
            diagnosis=payload.diagnosis or "Ayurvedic Consultation",
            symptoms=symptoms_text,
            notes=case_notes or "Prescription added from AI Vision OCR Decoder",
            ai_prescription=med_formatted_text,
            prakriti=getattr(patient, "prakriti", None) or "Tridosha Balance",
        )
        db.add(case)
        commit_with_retry(db)

        return {
            "success": True,
            "message": f"Prescription & Case Sheet successfully saved for {patient.name}!",
            "prescription_id": rx.id,
            "case_id": case.id,
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
            },
            "medicine_count": len(medicines_data),
        }

    except Exception as exc:
        logger.exception("Error saving prescription and case sheet: %s", exc)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save prescription: {str(exc)}")


@router.get("/prescriptions")
def get_all_prescriptions(
    patient_id: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve all saved prescriptions with linked patient and medicine details."""
    try:
        query = db.query(Prescription, Patient).outerjoin(Patient, Prescription.patient_id == Patient.id)

        if patient_id:
            query = query.filter(Prescription.patient_id == patient_id)

        if q and q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Patient.name.ilike(term),
                    Prescription.diagnosis.ilike(term),
                )
            )

        records = query.order_by(Prescription.created_at.desc()).limit(limit).all()

        results = []
        for rx, p in records:
            created_dt = rx.created_at
            
            # Normalize medicines list so legacy records with "name" and new records with "medicine_name" both work seamlessly
            normalized_medicines = []
            if isinstance(rx.medicines, list):
                for med in rx.medicines:
                    if isinstance(med, dict):
                        m_name = med.get("medicine_name") or med.get("name") or "Ayurvedic Formulation"
                        m_dur = str(med.get("duration") or "7").strip()
                        if m_dur.isdigit():
                            m_dur = f"{m_dur} days"
                        m_freq = med.get("frequency") or "1-0-1"
                        if m_freq.lower() in ("twice daily", "twice a day", "bd", "bid"):
                            m_freq = "1-0-1"
                        elif m_freq.lower() in ("three times daily", "tds", "tid"):
                            m_freq = "1-1-1"
                        elif m_freq.lower() in ("once daily", "od", "qd"):
                            m_freq = "1-0-0"
                        elif m_freq.lower() in ("at bedtime", "hs", "night"):
                            m_freq = "0-0-1"

                        normalized_medicines.append({
                            "medicine_name": m_name,
                            "name": m_name,
                            "dosage": med.get("dosage") or "1 unit",
                            "frequency": m_freq,
                            "duration": m_dur,
                            "instructions": med.get("instructions") or "With warm water",
                        })

            results.append({
                "id": rx.id,
                "patient_id": rx.patient_id,
                "patient_name": p.name if p else f"Patient #{rx.patient_id}",
                "patient_age": getattr(p, "age", None),
                "patient_gender": getattr(p, "gender", None),
                "patient_prakriti": getattr(p, "prakriti", "") or "Vata-Pitta",
                "diagnosis": rx.diagnosis or "Clinical Consultation",
                "medicines": normalized_medicines,
                "medicine_count": len(normalized_medicines),
                "advice": rx.advice or "",
                "created_at": created_dt.isoformat() if created_dt else None,
                "date_str": created_dt.strftime("%b %d, %Y") if created_dt else "Recent",
            })

        return {
            "success": True,
            "count": len(results),
            "prescriptions": results,
        }
    except Exception as exc:
        logger.exception("Error retrieving prescriptions: %s", exc)
        return {"success": False, "error": str(exc), "prescriptions": []}


@router.get("/case-sheets")
def get_all_case_sheets(
    patient_id: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve all clinical case sheets with patient details."""
    try:
        query = db.query(CaseSheet, Patient).outerjoin(Patient, CaseSheet.patient_id == Patient.id)

        if patient_id:
            query = query.filter(CaseSheet.patient_id == patient_id)

        if q and q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    Patient.name.ilike(term),
                    CaseSheet.diagnosis.ilike(term),
                    CaseSheet.symptoms.ilike(term),
                )
            )

        records = query.order_by(CaseSheet.created_at.desc()).limit(limit).all()

        results = []
        for c, p in records:
            created_dt = c.created_at
            results.append({
                "id": c.id,
                "patient_id": c.patient_id,
                "patient_name": p.name if p else f"Patient #{c.patient_id}",
                "patient_age": getattr(p, "age", None),
                "patient_gender": getattr(p, "gender", None),
                "diagnosis": c.diagnosis or "Clinical Consultation",
                "symptoms": c.symptoms or "",
                "notes": c.notes or "",
                "ai_prescription": c.ai_prescription or "",
                "prakriti": c.prakriti or "Vata-Pitta Imbalance",
                "created_at": created_dt.isoformat() if created_dt else None,
                "date_str": created_dt.strftime("%b %d, %Y") if created_dt else "Recent",
            })

        return {
            "success": True,
            "count": len(results),
            "case_sheets": results,
        }
    except Exception as exc:
        logger.exception("Error retrieving case sheets: %s", exc)
        return {"success": False, "error": str(exc), "case_sheets": []}


@router.get("/patients/list")
def get_patients_list(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve list of patients for selection dropdowns and AI chatbot."""
    try:
        query = db.query(Patient)
        if q and q.strip():
            query = query.filter(Patient.name.ilike(f"%{q.strip()}%"))

        patients = query.order_by(Patient.name.asc()).limit(50).all()

        raw_items = []
        for p in patients:
            rx_count = db.query(func.count(Prescription.id)).filter(Prescription.patient_id == p.id).scalar() or 0
            case_count = db.query(func.count(CaseSheet.id)).filter(CaseSheet.patient_id == p.id).scalar() or 0
            raw_items.append({
                "id": p.id,
                "name": p.name,
                "age": p.age,
                "gender": p.gender,
                "phone": p.phone or "",
                "prakriti": getattr(p, "prakriti", None) or "Vata-Pitta",
                "prescriptions_count": rx_count,
                "cases_count": case_count,
            })

        # Deduplicate by patient name (case-insensitive) to prevent repetitive dropdown/card entries
        seen_names = {}
        for item in raw_items:
            key = item["name"].strip().lower()
            if key not in seen_names:
                seen_names[key] = item
            else:
                # aggregate counts
                seen_names[key]["prescriptions_count"] += item["prescriptions_count"]
                seen_names[key]["cases_count"] += item["cases_count"]

        deduped = list(seen_names.values())
        return {"success": True, "patients": deduped}
    except Exception as exc:
        logger.exception("Error fetching patients list: %s", exc)
        return {"success": False, "patients": []}


@router.get("/patients/{patient_id}/dossier")
def get_patient_dossier(
    patient_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a complete clinical dossier for a specific patient."""
    try:
        patient = db.get(Patient, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        cases = db.query(CaseSheet).filter(CaseSheet.patient_id == patient_id).order_by(CaseSheet.created_at.desc()).all()
        prescriptions = db.query(Prescription).filter(Prescription.patient_id == patient_id).order_by(Prescription.created_at.desc()).all()
        appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).order_by(Appointment.date.desc()).all()

        return {
            "success": True,
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "phone": patient.phone,
                "prakriti": getattr(patient, "prakriti", "") or "Vata-Pitta",
            },
            "cases": [
                {
                    "id": c.id,
                    "diagnosis": c.diagnosis,
                    "symptoms": c.symptoms,
                    "notes": c.notes,
                    "ai_prescription": c.ai_prescription,
                    "date": c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
                }
                for c in cases
            ],
            "prescriptions": [
                {
                    "id": rx.id,
                    "diagnosis": rx.diagnosis,
                    "medicines": rx.medicines,
                    "advice": rx.advice,
                    "date": rx.created_at.strftime("%Y-%m-%d") if rx.created_at else "",
                }
                for rx in prescriptions
            ],
            "appointments": [
                {
                    "id": a.id,
                    "date": str(a.date),
                    "time": a.time,
                    "reason": a.reason,
                    "status": a.status,
                }
                for a in appointments
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error loading patient dossier: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ==========================================
# DOCTOR AI COPILOT CHATBOT ENDPOINT
# ==========================================

@router.post("/doctor/copilot-chat")
async def doctor_copilot_chat(
    payload: CopilotChatRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Doctor AI Clinical Copilot.
    Takes a question from the doctor, loads the relevant patient's full medical
    dossier (case sheets, prescriptions, medicines), and answers using Gemini 3.6 Flash.
    """
    message = payload.message.strip()
    if not message:
        return {"success": False, "reply": "Please enter a clinical question or patient inquiry."}

    # 1. Attempt to identify patient
    target_patient: Optional[Patient] = None
    if payload.patient_id:
        target_patient = db.get(Patient, payload.patient_id)

    if not target_patient and payload.patient_name:
        target_patient = (
            db.query(Patient)
            .filter(Patient.name.ilike(f"%{payload.patient_name.strip()}%"))
            .first()
        )

    # If still not specified, scan message for possible patient names
    if not target_patient:
        all_patients = db.query(Patient).limit(30).all()
        for p in all_patients:
            if p.name.lower() in message.lower():
                target_patient = p
                break

    # If no patient identified yet, prompt doctor to select a patient
    if not target_patient:
        recent_patients = db.query(Patient).limit(6).all()
        patient_chips = [
            {"id": p.id, "name": p.name, "age": p.age, "gender": p.gender}
            for p in recent_patients
        ]
        return {
            "success": True,
            "patient_selected": False,
            "reply": (
                "Namaste Doctor! I am your AI Clinical Copilot. Which patient would you like to review today? "
                "Select one of your patients below or type their name, and I will load their full case sheet history and prescriptions."
            ),
            "available_patients": patient_chips,
            "suggested_followups": [f"Review {p.name}" for p in recent_patients[:3]],
        }

    # 2. Patient identified: Load full dossier
    cases = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == target_patient.id)
        .order_by(CaseSheet.created_at.desc())
        .limit(10)
        .all()
    )
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.patient_id == target_patient.id)
        .order_by(Prescription.created_at.desc())
        .limit(10)
        .all()
    )

    # Build Clinical Dossier Context
    dossier_lines = [
        f"PATIENT DEMOGRAPHICS:",
        f"- Full Name: {target_patient.name}",
        f"- Age: {target_patient.age} | Gender: {target_patient.gender}",
        f"- Prakriti / Doshic State: {getattr(target_patient, 'prakriti', 'Vata-Pitta Imbalance')}",
        f"",
        f"CLINICAL CASE SHEETS ({len(cases)} on file):",
    ]

    if cases:
        for c in cases:
            date_str = c.created_at.strftime("%Y-%m-%d") if c.created_at else "Recent"
            dossier_lines.append(f"• [{date_str}] Diagnosis: {c.diagnosis}")
            if c.symptoms:
                dossier_lines.append(f"   Symptoms: {c.symptoms}")
            if c.notes:
                dossier_lines.append(f"   Doctor Notes: {c.notes}")
            if c.ai_prescription:
                dossier_lines.append(f"   Prescribed Medicines:\n{c.ai_prescription}")
    else:
        dossier_lines.append("• No prior case sheets recorded.")

    dossier_lines.append(f"\nSAVED PRESCRIPTIONS ({len(prescriptions)} on file):")
    if prescriptions:
        for rx in prescriptions:
            date_str = rx.created_at.strftime("%Y-%m-%d") if rx.created_at else "Recent"
            dossier_lines.append(f"• [Rx #{rx.id} on {date_str}] Diagnosis: {rx.diagnosis}")
            if rx.medicines and isinstance(rx.medicines, list):
                for m in rx.medicines:
                    dossier_lines.append(
                        f"   - {m.get('medicine_name')}: {m.get('dosage', '')} {m.get('frequency', '')} ({m.get('duration', '')}) | Notes: {m.get('instructions', '')}"
                    )
            if rx.advice:
                dossier_lines.append(f"   Advice: {rx.advice}")
    else:
        dossier_lines.append("• No prior prescriptions recorded.")

    dossier_context = "\n".join(dossier_lines)

    # 3. Construct System Prompt & Call Gemini 3.6 Flash
    system_prompt = (
        "You are Dr. Kash Clinical Copilot, an elite Ayurvedic Physician decision assistant supporting the treating doctor.\n"
        "You are provided with the patient's verified EMR case history, previous prescriptions, and doshic assessment.\n\n"
        f"=== PATIENT MEDICAL DOSSIER ===\n{dossier_context}\n================================\n\n"
        "Clinical Guidelines:\n"
        "1. Ground your answers strictly in this patient's case history and verified medications.\n"
        "2. When asked about past medications or symptoms, cite exact dates, names, and dosages from the dossier.\n"
        "3. Provide classical Ayurvedic reasoning (Dosha-Dhatu-Mala, Agni, Ama, Srotas).\n"
        "4. Highlight any herb-drug interactions, contraindications with existing medicines, or cautions.\n"
        "5. Recommend Pathya (beneficial foods/habits) and Apathya (foods to avoid).\n"
        "6. Maintain a professional, concise, structured tone appropriate for doctor-to-doctor clinical discussion.\n"
        "7. For prescription frequencies (e.g. 1-0-1, 1-1-1, 1-0-0, 0-0-1), clearly explain dosage timings by the 3 daily slots: Morning (Slot 1), Afternoon (Slot 2), and Night (Slot 3). For example, '1-0-1' means 1 dose in the Morning, 0 in the Afternoon (skip), and 1 dose at Night (Twice daily)."
    )

    try:
        reply_text = await call_gemini(
            prompt=message,
            system_prompt=system_prompt,
            temperature=0.3,
            max_output_tokens=1024,
        )
    except Exception as exc:
        logger.exception("Error calling Gemini for doctor copilot: %s", exc)
        # Fallback intelligent summary if Gemini times out
        reply_text = (
            f"**Patient Summary for {target_patient.name}**\n\n"
            f"- **Age/Gender**: {target_patient.age} / {target_patient.gender}\n"
            f"- **Recorded Diagnoses**: {', '.join(set(c.diagnosis for c in cases)) or 'General Consultation'}\n"
            f"- **Total Prescriptions**: {len(prescriptions)}\n"
            f"- **Active Case History**: {len(cases)} case sheets logged.\n\n"
            f"*(AI Engine temporarily busy, loaded directly from clinical EMR database)*"
        )

    # Relevant follow-up prompt chips for doctor
    suggested_followups = [
        f"Check contraindications for {target_patient.name}'s medicines",
        f"Recommend Pathya & Apathya diet for {target_patient.name}",
        f"Suggest Panchakarma protocol for this case",
        f"Summarize symptom progression over time",
    ]

    return {
        "success": True,
        "patient_selected": True,
        "patient": {
            "id": target_patient.id,
            "name": target_patient.name,
            "age": target_patient.age,
            "gender": target_patient.gender,
            "prakriti": getattr(target_patient, "prakriti", "Vata-Pitta"),
            "cases_count": len(cases),
            "prescriptions_count": len(prescriptions),
        },
        "reply": reply_text,
        "suggested_followups": suggested_followups,
    }
