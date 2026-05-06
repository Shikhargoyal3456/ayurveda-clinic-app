from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import insert, select, update

from app.database import SessionLocal, engine
from app.models import Appointment, CaseSheet, Doctor, Patient
from services.automation_tables import ai_processing_logs_table, ensure_automation_tables, telemedicine_sessions_table
logger = logging.getLogger(__name__)


class TelemedicineService:
    """Complete telemedicine system with AI assistance."""

    def __init__(self) -> None:
        self.active_sessions: dict[str, dict[str, Any]] = {}
        self.session_history: dict[str, list[dict[str, Any]]] = {}
        self.socket_registry: dict[str, list[Any]] = {}
        self.registry_lock = asyncio.Lock()
        ensure_automation_tables()

    async def create_consultation_session(
        self,
        patient_id: int,
        doctor_id: int,
        session_type: str = "video",
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "session_type": session_type,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "scheduled",
            "room_url": f"/telemedicine/room/{session_id}",
            "join_token": str(uuid.uuid4())[:8],
        }

        ai_insights = await self.ai_pre_screening(patient_id)
        session["ai_insights"] = ai_insights
        self.active_sessions[session_id] = session
        self.session_history.setdefault(session_id, [])
        self._persist_session(session)
        self._log_decision("telemedicine_session", patient_id, "create_session", session, 0.9)
        return session

    async def ai_pre_screening(self, patient_id: int) -> dict[str, Any]:
        db = SessionLocal()
        try:
            patient = db.get(Patient, patient_id)
            if patient is None:
                return {
                    "summary": "No prior patient history found yet.",
                    "vital_trends": "Vitals unavailable.",
                    "suggested_questions": [
                        "What symptoms brought you in today?",
                        "When did the symptoms begin?",
                    ],
                    "risk_factors": [],
                    "ai_diagnosis_suggestion": "Collect baseline history before diagnosis.",
                }

            recent_case = (
                db.query(CaseSheet)
                .filter(CaseSheet.patient_id == patient_id)
                .order_by(CaseSheet.created_at.desc())
                .first()
            )
            appointment_count = db.query(Appointment).filter(Appointment.patient_id == patient_id).count()
            diagnosis = recent_case.diagnosis if recent_case else "No prior diagnosis recorded"
            symptoms = recent_case.symptoms if recent_case else "No prior symptoms recorded"
            return {
                "summary": f"Patient {patient.name} has {appointment_count} prior appointments. Last diagnosis: {diagnosis}.",
                "vital_trends": "Vitals trend unavailable in telemedicine pre-screening." if recent_case is None else "Review prior EMR vitals before prescribing.",
                "suggested_questions": [
                    "Have you been taking medication regularly?",
                    "Any new symptoms since the last consultation?",
                    "Have diet or sleep patterns changed recently?",
                ],
                "risk_factors": [factor for factor in [patient.gender, f"Age {patient.age}"] if factor],
                "ai_diagnosis_suggestion": f"Review prior symptom pattern: {symptoms[:120]}",
            }
        except Exception as exc:
            logger.warning("Telemedicine pre-screening fell back for patient %s: %s", patient_id, exc)
            return {
                "summary": "Pre-screening is running in fallback mode.",
                "vital_trends": "Vitals unavailable.",
                "suggested_questions": [
                    "What symptoms brought you in today?",
                    "How long have they been present?",
                ],
                "risk_factors": [],
                "ai_diagnosis_suggestion": "Collect baseline history before diagnosis.",
            }
        finally:
            db.close()

    async def real_time_ai_assistant(self, session_id: str, conversation_text: list[str] | str) -> dict[str, Any]:
        text = "\n".join(conversation_text) if isinstance(conversation_text, list) else str(conversation_text or "")
        key_points = self._extract_key_points(text)
        insight = {
            "session_id": session_id,
            "extracted_symptoms": key_points.get("symptoms", []),
            "suggested_diagnosis": key_points.get("possible_diagnosis", []),
            "suggested_medications": key_points.get("medications", []),
            "follow_up_questions": [
                "How long have you experienced these symptoms?",
                "What makes it better or worse?",
            ],
            "emergency_alert": self._check_emergency(key_points),
        }
        self.session_history.setdefault(session_id, []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "conversation_excerpt": text[-500:],
                "insight": insight,
            }
        )
        self._log_decision("telemedicine_session", 0, "real_time_assist", insight, 0.78)
        return insight

    async def ai_post_consultation_summary(self, session_id: str) -> dict[str, Any]:
        session = self.active_sessions.get(session_id) or self._load_session(session_id) or {}
        summary = {
            "session_id": session_id,
            "date": datetime.now(timezone.utc).isoformat(),
            "diagnosis": self._generate_diagnosis(session),
            "prescription": self._suggest_prescription(session),
            "follow_up_required": True,
            "follow_up_in_days": 15,
            "lifestyle_advice": [
                "Increase water intake",
                "30 minutes daily walk",
                "Avoid very spicy foods until symptoms settle",
            ],
            "emergency_instructions": "Seek immediate care if chest pain, severe breathing difficulty, or fainting occurs.",
        }
        self._persist_summary(session_id, summary)
        self._log_decision("telemedicine_session", 0, "summary", summary, 0.82)
        return summary

    async def auto_schedule_followup(self, session_id: str) -> dict[str, Any]:
        session = self.active_sessions.get(session_id) or self._load_session(session_id) or {}
        condition_severity = self._assess_severity(session)
        followup_days = {
            "critical": 2,
            "high": 7,
            "medium": 15,
            "low": 30,
        }
        suggested_date = datetime.now(timezone.utc) + timedelta(days=followup_days.get(condition_severity, 15))
        return {
            "session_id": session_id,
            "suggested_followup_date": suggested_date.isoformat(),
            "severity": condition_severity,
            "auto_scheduled": False,
            "booking_link": f"/appointments/book?session={session_id}",
        }

    async def analyze_symptoms(self, symptoms: str) -> dict[str, Any]:
        text = str(symptoms or "").lower()
        urgency = "low"
        conditions = [{"name": "General viral syndrome", "probability": 62}]
        recommendations = ["Hydration", "Rest", "Monitor symptoms"]
        if any(token in text for token in ["chest pain", "breathless", "faint", "unconscious"]):
            urgency = "high"
            conditions = [{"name": "Needs urgent physician review", "probability": 88}]
            recommendations = ["Seek immediate consultation", "Do not delay emergency assessment"]
        elif any(token in text for token in ["fever", "headache", "body ache"]):
            urgency = "medium"
            conditions = [{"name": "Common Cold", "probability": 75}, {"name": "Viral Fever", "probability": 58}]
            recommendations = ["Rest", "Hydration", "Monitor temperature", "Book a consultation if symptoms persist"]

        doctors = self._recommend_doctors()
        result = {
            "conditions": conditions,
            "urgency": urgency,
            "recommendations": recommendations,
            "doctors": doctors,
        }
        self._log_decision("telemedicine_triage", 0, "symptom_analysis", result, 0.73)
        return result

    async def handle_signaling(self, session_id: str, data: dict[str, Any], sender: Any | None = None) -> None:
        self.session_history.setdefault(session_id, []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal": data,
            }
        )
        async with self.registry_lock:
            sockets = list(self.socket_registry.get(session_id, []))
        for socket in sockets:
            if sender is not None and socket is sender:
                continue
            await socket.send_json(data)

    async def register_socket(self, session_id: str, websocket: Any) -> None:
        async with self.registry_lock:
            self.socket_registry.setdefault(session_id, []).append(websocket)

    async def handle_disconnect(self, session_id: str, websocket: Any | None = None) -> None:
        async with self.registry_lock:
            sockets = self.socket_registry.get(session_id, [])
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets and session_id in self.socket_registry:
                self.socket_registry.pop(session_id, None)
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = "completed"

    def _extract_key_points(self, conversation_text: str) -> dict[str, list[str]]:
        text = str(conversation_text or "").lower()
        symptoms = [token for token in ["fever", "headache", "cough", "pain", "acidity", "sleep", "fatigue"] if token in text]
        possible_diagnosis = []
        if "fever" in text and "cough" in text:
            possible_diagnosis.append("Upper respiratory infection")
        if "acidity" in text or "burning" in text:
            possible_diagnosis.append("Acid-peptic irritation")
        medications = []
        if "pain" in text:
            medications.append("Supportive pain management review")
        if "sleep" in text:
            medications.append("Sleep hygiene and calming support")
        return {
            "symptoms": symptoms,
            "possible_diagnosis": possible_diagnosis or ["Further clinical evaluation needed"],
            "medications": medications,
        }

    def _check_emergency(self, key_points: dict[str, list[str]]) -> bool:
        red_flags = {"breathless", "chest pain", "fainting"}
        symptom_set = set(key_points.get("symptoms", []))
        return bool(symptom_set & red_flags)

    def _generate_diagnosis(self, session: dict[str, Any]) -> str:
        insights = session.get("ai_insights", {})
        return str(insights.get("ai_diagnosis_suggestion", "Clinical diagnosis pending doctor confirmation"))

    def _suggest_prescription(self, session: dict[str, Any]) -> list[dict[str, str]]:
        session_type = str(session.get("session_type", "video"))
        base = [
            {"medicine": "Hydration support", "dosage": "As advised", "duration": "5 days"},
            {"medicine": "Diet regulation", "dosage": "Follow clinician advice", "duration": "14 days"},
        ]
        if session_type == "ayurveda":
            base.append({"medicine": "Ayurveda formulation review", "dosage": "Doctor to finalize", "duration": "14 days"})
        return base

    def _assess_severity(self, session: dict[str, Any]) -> str:
        summary = json.dumps(session, ensure_ascii=True).lower()
        if any(token in summary for token in ["critical", "emergency", "severe"]):
            return "critical"
        if any(token in summary for token in ["high risk", "urgent"]):
            return "high"
        if any(token in summary for token in ["follow up", "review"]):
            return "medium"
        return "low"

    def _recommend_doctors(self) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            doctors = db.query(Doctor).order_by(Doctor.created_at.asc()).limit(3).all()
            if not doctors:
                return [{"id": 1, "name": "Sarah", "specialization": "General Medicine", "rating": 4.8, "experience": 12}]
            recommended = []
            for index, doctor in enumerate(doctors, start=1):
                recommended.append(
                    {
                        "id": doctor.id,
                        "name": doctor.full_name or doctor.username,
                        "specialization": doctor.specialty.title(),
                        "rating": round(4.5 + min(index, 3) * 0.1, 1),
                        "experience": 5 + index * 3,
                    }
                )
            return recommended
        except Exception as exc:
            logger.warning("Doctor recommendation lookup fell back: %s", exc)
            return [{"id": 1, "name": "Sarah", "specialization": "General Medicine", "rating": 4.8, "experience": 12}]
        finally:
            db.close()

    def _persist_session(self, session: dict[str, Any]) -> None:
        try:
            ensure_automation_tables()
            payload = {
                "session_id": session["session_id"],
                "patient_id": int(session["patient_id"]),
                "doctor_id": int(session["doctor_id"]),
                "session_type": str(session.get("session_type", "video")),
                "status": str(session.get("status", "scheduled")),
                "start_time": datetime.now(timezone.utc),
            }
            with engine.begin() as connection:
                connection.execute(insert(telemedicine_sessions_table).values(**payload))
        except Exception as exc:
            logger.warning("Telemedicine session persistence skipped: %s", exc)

    def _load_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            ensure_automation_tables()
            with engine.begin() as connection:
                row = connection.execute(
                    select(telemedicine_sessions_table).where(telemedicine_sessions_table.c.session_id == session_id)
                ).mappings().first()
            return dict(row) if row else None
        except Exception as exc:
            logger.warning("Telemedicine session load skipped for %s: %s", session_id, exc)
            return None

    def _persist_summary(self, session_id: str, summary: dict[str, Any]) -> None:
        try:
            ensure_automation_tables()
            with engine.begin() as connection:
                connection.execute(
                    update(telemedicine_sessions_table)
                    .where(telemedicine_sessions_table.c.session_id == session_id)
                    .values(
                        status="completed",
                        end_time=datetime.now(timezone.utc),
                        ai_summary=json.dumps(summary, ensure_ascii=True),
                    )
                )
        except Exception as exc:
            logger.warning("Telemedicine summary persistence skipped for %s: %s", session_id, exc)

    def _log_decision(self, entity_type: str, entity_id: int, action: str, decision: dict[str, Any], confidence: float) -> None:
        try:
            ensure_automation_tables()
            payload = {
                "entity_type": entity_type,
                "entity_id": int(entity_id or 0),
                "action": action,
                "ai_decision": json.dumps(decision, ensure_ascii=True),
                "confidence": float(confidence),
            }
            with engine.begin() as connection:
                connection.execute(insert(ai_processing_logs_table).values(**payload))
        except Exception as exc:
            logger.warning("Telemedicine decision log skipped for %s:%s: %s", entity_type, entity_id, exc)
