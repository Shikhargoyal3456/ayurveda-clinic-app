from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.models import CaseSheet, Doctor, Patient
from models.audit_log import AuditLog
from models.payment import Payment
from models.prescription import Prescription

try:
    import fitz
except Exception:  # pragma: no cover
    fitz = None


@dataclass
class ExportPayload:
    filename: str
    content: bytes
    media_type: str


class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def _csv_response(self, rows: list[dict[str, Any]], filename: str) -> ExportPayload:
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        content = buffer.getvalue().encode("utf-8")
        return ExportPayload(filename=filename, content=content, media_type="text/csv")

    def _pdf_response(self, title: str, lines: list[str], filename: str) -> ExportPayload:
        if fitz is None:
            raise HTTPException(status_code=503, detail="PDF export unavailable")
        document = fitz.open()
        page = document.new_page()
        y = 48
        page.insert_text((48, y), title, fontsize=18)
        y += 32
        for line in lines:
            page.insert_text((48, y), line, fontsize=11)
            y += 18
        content = document.tobytes()
        document.close()
        return ExportPayload(filename=filename, content=content, media_type="application/pdf")

    def export_patients_csv(self, doctor: Doctor) -> ExportPayload:
        rows = [
            {
                "id": patient.id,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "phone": patient.phone,
                "email": patient.email,
                "created_at": patient.created_at.isoformat() if patient.created_at else "",
            }
            for patient in self.db.query(Patient).filter(Patient.doctor_id == doctor.id).order_by(Patient.id.desc()).all()
        ]
        return self._csv_response(rows, "patients_export.csv")

    def export_patient_pdf(self, doctor: Doctor, patient_id: int) -> ExportPayload:
        patient = self.db.query(Patient).filter(Patient.id == patient_id, Patient.doctor_id == doctor.id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        cases = self.db.query(CaseSheet).filter(CaseSheet.patient_id == patient.id).order_by(CaseSheet.created_at.desc()).all()
        prescriptions = self.db.query(Prescription).filter(Prescription.patient_id == patient.id).order_by(Prescription.created_at.desc()).all()
        payments = self.db.query(Payment).filter(Payment.patient_id == patient.id).order_by(Payment.date.desc()).all()
        lines = [
            f"Patient ID: {patient.id}",
            f"Age: {patient.age}",
            f"Phone: {patient.phone or '—'}",
            f"Email: {patient.email or '—'}",
            "",
            f"Cases: {len(cases)}",
            f"Prescriptions: {len(prescriptions)}",
            f"Payments: {len(payments)}",
        ]
        return self._pdf_response(f"Patient Record: {patient.name}", lines, f"patient_{patient.id}.pdf")

    def export_prescription_pdf(self, doctor: Doctor, prescription_id: int) -> ExportPayload:
        prescription = (
            self.db.query(Prescription)
            .filter(Prescription.id == prescription_id, Prescription.doctor_id == doctor.id)
            .first()
        )
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        lines = [
            f"Patient: {prescription.patient.name}",
            f"Diagnosis: {prescription.diagnosis}",
            f"Medicines: {json.dumps(prescription.medicines or [], ensure_ascii=True)}",
            f"Advice: {prescription.advice or '—'}",
        ]
        return self._pdf_response(f"Prescription #{prescription.id}", lines, f"prescription_{prescription.id}.pdf")

    def export_all_data(self, doctor: Doctor | None = None) -> ExportPayload:
        patient_query = self.db.query(Patient)
        prescription_query = self.db.query(Prescription)
        case_query = self.db.query(CaseSheet)
        if doctor is not None:
            patient_query = patient_query.filter(Patient.doctor_id == doctor.id)
            prescription_query = prescription_query.filter(Prescription.doctor_id == doctor.id)
            case_query = case_query.join(Patient).filter(Patient.doctor_id == doctor.id)
        payload = {
            "patients": [patient.id for patient in patient_query.all()],
            "prescriptions": [item.id for item in prescription_query.all()],
            "cases": [item.id for item in case_query.all()],
            "generated_at": datetime.utcnow().isoformat(),
        }
        return ExportPayload(
            filename="all_data_export.json",
            content=json.dumps(payload, indent=2).encode("utf-8"),
            media_type="application/json",
        )

    def build_response(self, payload: ExportPayload) -> Response:
        return Response(
            content=payload.content,
            media_type=payload.media_type,
            headers={"Content-Disposition": f'attachment; filename="{payload.filename}"'},
        )
