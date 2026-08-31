from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models import Appointment, CaseSheet, Doctor, Patient
from models.emr import EMRConsultation, EMRLabOrder, EMROutcome, EMRPrescription
from models.outcome import Outcome
from models.payment import Payment
from services.ai_provider import call_gemini, parse_json_response
from services.cache_service import cache_result


logger = logging.getLogger(__name__)

ACTION_CATALOG = {
    "register_patient": {"label": "Register Patient", "url": "/emr/patient-registration"},
    "open_registry": {"label": "Open Patient Registry", "url": "/emr/patient-registry"},
    "review_schedule": {"label": "Review Schedule", "url": "/appointments"},
    "open_emr": {"label": "Open EMR", "url": "/emr/doctor-dashboard"},
    "write_prescription": {"label": "Write Prescription", "url": "/emr/patient-registry"},
    "review_followups": {"label": "Review Follow-ups", "url": "/followups"},
    "review_payments": {"label": "Review Payments", "url": "/payments/daily"},
    "review_labs": {"label": "Review Labs", "url": "/emr/lab-dashboard"},
    "open_ai_scribe": {"label": "Open AI Scribe", "url": "/emr/ambient-scribe"},
}


def _safe_date(value: Any) -> str | None:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None


def _days_since(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return (date.today() - value).days
    return None


def build_doctor_dashboard_snapshot(db: Session, doctor_id: int) -> dict[str, Any]:
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    doctor = db.get(Doctor, doctor_id)
    patients = (
        db.query(Patient)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(Patient.created_at.desc(), Patient.id.desc())
        .all()
    )
    appointments = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )
    cases = (
        db.query(CaseSheet)
        .join(Patient, Patient.id == CaseSheet.patient_id)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
        .all()
    )
    prescriptions = (
        db.query(EMRPrescription)
        .filter(EMRPrescription.doctor_id == doctor_id)
        .order_by(EMRPrescription.created_at.desc(), EMRPrescription.id.desc())
        .all()
    )
    labs = (
        db.query(EMRLabOrder)
        .filter(EMRLabOrder.doctor_id == doctor_id)
        .order_by(EMRLabOrder.ordered_at.desc(), EMRLabOrder.id.desc())
        .all()
    )
    emr_outcomes = (
        db.query(EMROutcome)
        .join(Patient, Patient.id == EMROutcome.patient_id)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(EMROutcome.recorded_at.desc(), EMROutcome.id.desc())
        .all()
    )
    outcomes = (
        db.query(Outcome)
        .join(Patient, Patient.id == Outcome.patient_id)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(Outcome.date.desc(), Outcome.id.desc())
        .all()
    )
    payments = (
        db.query(Payment)
        .join(Patient, Patient.id == Payment.patient_id)
        .filter(Patient.doctor_id == doctor_id)
        .order_by(Payment.date.desc(), Payment.id.desc())
        .all()
    )

    patient_lookup = {patient.id: patient for patient in patients}
    cases_by_patient: dict[int, list[CaseSheet]] = defaultdict(list)
    for item in cases:
        cases_by_patient[item.patient_id].append(item)

    appointments_by_patient: dict[int, list[Appointment]] = defaultdict(list)
    for item in appointments:
        appointments_by_patient[item.patient_id].append(item)

    labs_by_patient: dict[int, list[EMRLabOrder]] = defaultdict(list)
    for item in labs:
        labs_by_patient[item.patient_id].append(item)

    prescriptions_by_patient: dict[int, list[EMRPrescription]] = defaultdict(list)
    for item in prescriptions:
        prescriptions_by_patient[item.patient_id].append(item)

    legacy_outcomes_by_patient: dict[int, list[Outcome]] = defaultdict(list)
    for item in outcomes:
        legacy_outcomes_by_patient[item.patient_id].append(item)

    emr_outcomes_by_patient: dict[int, list[EMROutcome]] = defaultdict(list)
    for item in emr_outcomes:
        emr_outcomes_by_patient[item.patient_id].append(item)

    patient_data: list[dict[str, Any]] = []
    for patient in patients:
        patient_cases = cases_by_patient.get(patient.id, [])
        patient_appointments = appointments_by_patient.get(patient.id, [])
        patient_labs = labs_by_patient.get(patient.id, [])
        patient_prescriptions = prescriptions_by_patient.get(patient.id, [])
        patient_legacy_outcomes = legacy_outcomes_by_patient.get(patient.id, [])
        patient_emr_outcomes = emr_outcomes_by_patient.get(patient.id, [])

        completed_appointments = [
            item for item in patient_appointments
            if str(item.status or "").strip().lower() in {"completed", "done", "closed"}
        ]
        overdue_followups = [
            item for item in patient_cases
            if item.followup_date and item.followup_date <= today
        ]
        pending_labs = [
            item for item in patient_labs
            if str(item.status or "").strip().lower() != "completed"
        ]
        latest_case = patient_cases[0] if patient_cases else None
        latest_outcome = patient_legacy_outcomes[0] if patient_legacy_outcomes else None
        latest_emr_outcome = patient_emr_outcomes[0] if patient_emr_outcomes else None
        latest_lab = patient_labs[0] if patient_labs else None

        patient_data.append(
            {
                "patient_id": patient.id,
                "name": patient.name,
                "age": patient.age,
                "gender": patient.gender,
                "is_new": bool(patient.created_at and patient.created_at.date() >= week_ago),
                "active_cases": len(patient_cases),
                "appointments_total": len(patient_appointments),
                "appointments_completed": len(completed_appointments),
                "appointments_scheduled": len(
                    [
                        item for item in patient_appointments
                        if str(item.status or "").strip().lower() in {"scheduled", "confirmed", "upcoming"}
                    ]
                ),
                "overdue_followups": len(overdue_followups),
                "pending_labs": len(pending_labs),
                "prescriptions_count": len(patient_prescriptions),
                "last_visit_days_ago": _days_since(
                    max((item.date for item in patient_appointments if item.date), default=None)
                ),
                "latest_case_diagnosis": latest_case.diagnosis if latest_case else "",
                "latest_case_notes": latest_case.followup_notes if latest_case else "",
                "latest_outcome_status": latest_outcome.improvement_status if latest_outcome else "",
                "latest_symptom_score": latest_outcome.symptom_score if latest_outcome else None,
                "avg_emr_improvement": round(
                    mean([item.improvement_percentage for item in patient_emr_outcomes]),
                    2,
                )
                if patient_emr_outcomes
                else None,
                "avg_emr_rating": round(mean([item.rating for item in patient_emr_outcomes]), 2)
                if patient_emr_outcomes
                else None,
                "latest_emr_outcome_note": latest_emr_outcome.notes if latest_emr_outcome else "",
                "latest_lab_status": latest_lab.status if latest_lab else "",
            }
        )

    appointment_data = [
        {
            "id": item.id,
            "patient_id": item.patient_id,
            "patient_name": item.patient.name if item.patient else (
                patient_lookup[item.patient_id].name if item.patient_id in patient_lookup else "Patient"
            ),
            "date": _safe_date(item.date),
            "time": item.time,
            "status": item.status,
            "reason": item.reason,
            "is_today": bool(item.date == today),
            "is_past": bool(item.date and item.date < today),
        }
        for item in appointments[:40]
    ]

    aggregate = {
        "doctor_id": doctor_id,
        "doctor_name": doctor.full_name if doctor else "Doctor",
        "specialty": doctor.specialty if doctor else "",
        "total_patients": len(patients),
        "new_patients_this_week": len([item for item in patients if item.created_at and item.created_at.date() >= week_ago]),
        "appointments_today": len([item for item in appointments if item.date == today]),
        "appointments_this_month": len([item for item in appointments if item.date and item.date >= month_ago]),
        "completed_appointments": len(
            [item for item in appointments if str(item.status or "").strip().lower() in {"completed", "done", "closed"}]
        ),
        "scheduled_appointments": len(
            [item for item in appointments if str(item.status or "").strip().lower() in {"scheduled", "confirmed", "upcoming"}]
        ),
        "overdue_followups": len(
            [item for item in cases if item.followup_date and item.followup_date <= today]
        ),
        "pending_lab_orders": len(
            [item for item in labs if str(item.status or "").strip().lower() != "completed"]
        ),
        "avg_emr_improvement": round(mean([item.improvement_percentage for item in emr_outcomes]), 2)
        if emr_outcomes
        else None,
        "avg_outcome_rating": round(mean([item.rating for item in emr_outcomes]), 2)
        if emr_outcomes
        else None,
        "avg_symptom_score": round(mean([item.symptom_score for item in outcomes]), 2)
        if outcomes
        else None,
        "pending_payments": len(
            [item for item in payments if str(item.status or "").strip().lower() == "unpaid"]
        ),
        "paid_payments_today": round(
            sum(float(item.amount or 0) for item in payments if item.date == today and str(item.status or "").strip().lower() == "paid"),
            2,
        ),
        "prescriptions_issued": len(prescriptions),
    }
    return {
        "aggregate": aggregate,
        "patient_data": patient_data,
        "appointment_data": appointment_data,
    }


def _bounded_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _fallback_actions(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    aggregate = snapshot["aggregate"]
    actions: list[dict[str, str]] = []
    if aggregate["overdue_followups"] > 0:
        actions.append({"action_key": "review_followups", "reason": "Overdue follow-ups need outreach today."})
    if aggregate["pending_lab_orders"] > 0:
        actions.append({"action_key": "review_labs", "reason": "Pending lab orders may block treatment decisions."})
    if aggregate["appointments_today"] > 0:
        actions.append({"action_key": "review_schedule", "reason": "Today's appointment list still needs active tracking."})
    if not actions:
        actions.append({"action_key": "open_registry", "reason": "Review patient records and identify next care opportunities."})
    return actions[:3]


def _fallback_alerts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for patient in snapshot["patient_data"]:
        if patient["overdue_followups"] > 0:
            alerts.append(
                {
                    "patient_id": patient["patient_id"],
                    "patient_name": patient["name"],
                    "alert_type": "follow-up",
                    "urgency": "high" if patient["overdue_followups"] > 1 else "medium",
                    "reason": f"{patient['overdue_followups']} follow-up item(s) are due.",
                }
            )
        elif patient["pending_labs"] > 0:
            alerts.append(
                {
                    "patient_id": patient["patient_id"],
                    "patient_name": patient["name"],
                    "alert_type": "abnormal",
                    "urgency": "medium",
                    "reason": f"{patient['pending_labs']} lab result(s) still need review.",
                }
            )
    return alerts[:5]


def _get_fallback_insights(snapshot: dict[str, Any]) -> dict[str, Any]:
    aggregate = snapshot["aggregate"]
    total_relevant_appointments = max(
        1,
        aggregate["completed_appointments"] + aggregate["scheduled_appointments"],
    )
    adherence_rate = aggregate["completed_appointments"] / total_relevant_appointments
    outcome_improvement = float(aggregate["avg_emr_improvement"] or 60)
    care_rating = (float(aggregate["avg_outcome_rating"] or 3.5) / 5) * 100
    symptom_score = float(aggregate["avg_symptom_score"] or 5)

    health_score = _bounded_score((adherence_rate * 40) + (outcome_improvement * 0.4) + (max(0, 10 - symptom_score) * 6))
    care_score = _bounded_score((care_rating * 0.5) + (outcome_improvement * 0.35) + (adherence_rate * 15))

    priorities: list[str] = []
    if aggregate["overdue_followups"] > 0:
        priorities.append(f"Reconnect with {aggregate['overdue_followups']} patient follow-up(s) that are already due.")
    if aggregate["pending_lab_orders"] > 0:
        priorities.append(f"Review {aggregate['pending_lab_orders']} pending lab order(s) before they delay care decisions.")
    if aggregate["pending_payments"] > 0:
        priorities.append(f"Close the loop on {aggregate['pending_payments']} unpaid payment(s) affecting the treatment journey.")
    if aggregate["appointments_today"] > 0:
        priorities.append(f"Prepare for {aggregate['appointments_today']} scheduled appointment(s) on today's roster.")
    if not priorities:
        priorities.append("No major bottleneck is visible, so today is ideal for proactive patient outreach and documentation cleanup.")

    message_bits = [
        f"{aggregate['appointments_today']} appointment(s) on the calendar",
        f"{aggregate['new_patients_this_week']} new patient(s) this week",
    ]
    if aggregate["avg_emr_improvement"] is not None:
        message_bits.append(f"{round(float(aggregate['avg_emr_improvement']))}% average tracked improvement")

    recommended_action = _fallback_actions(snapshot)[0]["action_key"]
    return {
        "health_score": health_score,
        "care_score": care_score,
        "health_score_factors": [
            f"Appointment adherence is tracking at {round(adherence_rate * 100)}%.",
            f"Average documented improvement is {round(outcome_improvement)}%.",
        ],
        "care_score_factors": [
            f"Average care rating proxy is {round(care_rating)}%.",
            f"Symptom burden proxy is {round(symptom_score, 1)}/10 across recorded outcomes.",
        ],
        "daily_message": "Today's clinic picture is built from " + ", ".join(message_bits) + ".",
        "top_priorities": priorities[:3],
        "patient_alerts": _fallback_alerts(snapshot),
        "insight": (
            f"Tracked outcomes show {'positive' if health_score >= 70 else 'mixed'} momentum, "
            f"with {aggregate['overdue_followups']} overdue follow-up(s) and {aggregate['pending_lab_orders']} pending lab order(s)."
        ),
        "recommendation": priorities[0],
        "recommended_action": recommended_action,
        "dashboard_actions": _fallback_actions(snapshot),
    }


class AIDashboardIntelligence:
    """AI-generated dashboard insights grounded in live doctor data."""

    @cache_result(ttl=300)
    async def generate_dashboard_insights(
        self,
        doctor_id: int,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        aggregate = snapshot["aggregate"]
        patient_data = snapshot["patient_data"]
        appointment_data = snapshot["appointment_data"]
        prompt = f"""
You are an AI healthcare analytics assistant helping a doctor review today's clinic performance.
Use only the live data below. Do not invent fake totals or generic filler.

DOCTOR CONTEXT:
{json.dumps(aggregate, indent=2)}

PATIENT SNAPSHOT:
{json.dumps(patient_data[:12], indent=2)}

APPOINTMENT SNAPSHOT:
{json.dumps(appointment_data[:20], indent=2)}

AVAILABLE ACTION KEYS:
{json.dumps(list(ACTION_CATALOG.keys()), indent=2)}

SCORING GUIDANCE:
- HEALTH SCORE should reflect patient outcomes, appointment adherence, follow-up discipline, and unresolved blockers.
- CARE SCORE should reflect treatment effectiveness, outcome quality, symptom improvement, and feedback/rating proxies.
- TOP PRIORITIES must be specific to this practice today.
- PATIENT ALERTS must refer to real patients from the snapshot and include patient_id.
- DASHBOARD ACTIONS must choose 1 to 3 action_key values from the allowed list.
- Avoid generic phrases like "balanced flow" or "steady consultations."

Return ONLY valid JSON with this exact schema:
{{
  "health_score": 0,
  "care_score": 0,
  "health_score_factors": ["factor 1", "factor 2"],
  "care_score_factors": ["factor 1", "factor 2"],
  "daily_message": "personalized message",
  "top_priorities": ["priority 1", "priority 2", "priority 3"],
  "patient_alerts": [
    {{
      "patient_id": 0,
      "patient_name": "",
      "alert_type": "follow-up|abnormal|medication|outcome",
      "urgency": "high|medium|low",
      "reason": ""
    }}
  ],
  "insight": "key performance insight",
  "recommendation": "one concrete recommendation for today",
  "recommended_action": "one action_key from the allowed list",
  "dashboard_actions": [
    {{
      "action_key": "one action key from allowed list",
      "reason": "why this action matters today"
    }}
  ]
}}
"""
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a precise healthcare analytics assistant. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=1800,
            )
            payload = parse_json_response(response)
            return self._normalize_dashboard_payload(payload, snapshot)
        except Exception as exc:
            logger.warning("AI dashboard generation failed for doctor_id=%s: %s", doctor_id, exc)
            return _get_fallback_insights(snapshot)

    async def generate_ai_recommendations(self, patient_id: int, case_data: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are an AI care planning assistant. Review this real patient case and recommend the next best step.

PATIENT CASE:
{json.dumps(case_data, indent=2)}

Return ONLY valid JSON:
{{
  "recommended_action": "Schedule follow-up|Order tests|Review medications|Call patient|Update care plan",
  "urgency": "high|medium|low",
  "reason": "grounded reasoning based on the case data",
  "suggested_days": 0
}}
"""
        try:
            response = await call_gemini(
                prompt,
                system_prompt="You are a careful clinical workflow assistant. Return JSON only.",
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=600,
            )
            payload = parse_json_response(response)
            return {
                "recommended_action": str(payload.get("recommended_action") or "Review medications"),
                "urgency": str(payload.get("urgency") or "medium"),
                "reason": str(payload.get("reason") or "Case review is recommended based on the latest data."),
                "suggested_days": max(0, int(payload.get("suggested_days") or 7)),
            }
        except Exception as exc:
            logger.warning("AI patient recommendation failed for patient_id=%s: %s", patient_id, exc)
            return {
                "recommended_action": "Schedule follow-up",
                "urgency": "medium",
                "reason": "The latest case data indicates that a doctor review should not be deferred.",
                "suggested_days": 7,
            }

    def _normalize_dashboard_payload(self, payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        fallback = _get_fallback_insights(snapshot)
        normalized = {
            "health_score": _bounded_score(float(payload.get("health_score", fallback["health_score"]))),
            "care_score": _bounded_score(float(payload.get("care_score", fallback["care_score"]))),
            "health_score_factors": [
                str(item).strip() for item in (payload.get("health_score_factors") or fallback["health_score_factors"]) if str(item).strip()
            ][:3],
            "care_score_factors": [
                str(item).strip() for item in (payload.get("care_score_factors") or fallback["care_score_factors"]) if str(item).strip()
            ][:3],
            "daily_message": str(payload.get("daily_message") or fallback["daily_message"]).strip(),
            "top_priorities": [
                str(item).strip() for item in (payload.get("top_priorities") or fallback["top_priorities"]) if str(item).strip()
            ][:3],
            "patient_alerts": self._normalize_alerts(payload.get("patient_alerts"), snapshot) or fallback["patient_alerts"],
            "insight": str(payload.get("insight") or fallback["insight"]).strip(),
            "recommendation": str(payload.get("recommendation") or fallback["recommendation"]).strip(),
            "recommended_action": str(payload.get("recommended_action") or fallback["recommended_action"]).strip(),
            "dashboard_actions": self._normalize_actions(payload.get("dashboard_actions")) or fallback["dashboard_actions"],
        }
        if normalized["recommended_action"] not in ACTION_CATALOG:
            normalized["recommended_action"] = fallback["recommended_action"]
        return normalized

    def _normalize_alerts(self, alerts: Any, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        valid_patients = {item["patient_id"]: item["name"] for item in snapshot["patient_data"]}
        normalized: list[dict[str, Any]] = []
        for item in alerts or []:
            if not isinstance(item, dict):
                continue
            try:
                patient_id = int(item.get("patient_id") or 0)
            except (TypeError, ValueError):
                patient_id = 0
            if patient_id not in valid_patients:
                continue
            urgency = str(item.get("urgency") or "medium").strip().lower()
            if urgency not in {"high", "medium", "low"}:
                urgency = "medium"
            normalized.append(
                {
                    "patient_id": patient_id,
                    "patient_name": str(item.get("patient_name") or valid_patients[patient_id]).strip() or valid_patients[patient_id],
                    "alert_type": str(item.get("alert_type") or "follow-up").strip().lower(),
                    "urgency": urgency,
                    "reason": str(item.get("reason") or "").strip(),
                }
            )
        return normalized[:5]

    def _normalize_actions(self, actions: Any) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in actions or []:
            if not isinstance(item, dict):
                continue
            action_key = str(item.get("action_key") or "").strip()
            if action_key not in ACTION_CATALOG:
                continue
            normalized.append(
                {
                    "action_key": action_key,
                    "reason": str(item.get("reason") or "").strip() or f"{ACTION_CATALOG[action_key]['label']} is recommended by AI.",
                }
            )
        return normalized[:3]


def build_patient_case_snapshot(db: Session, patient_id: int) -> dict[str, Any] | None:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return None
    latest_case = (
        db.query(CaseSheet)
        .filter(CaseSheet.patient_id == patient_id)
        .order_by(CaseSheet.created_at.desc(), CaseSheet.id.desc())
        .first()
    )
    latest_consultation = (
        db.query(EMRConsultation)
        .filter(EMRConsultation.patient_id == patient_id)
        .order_by(EMRConsultation.created_at.desc(), EMRConsultation.id.desc())
        .first()
    )
    latest_outcome = (
        db.query(Outcome)
        .filter(Outcome.patient_id == patient_id)
        .order_by(Outcome.date.desc(), Outcome.id.desc())
        .first()
    )
    latest_emr_outcome = (
        db.query(EMROutcome)
        .filter(EMROutcome.patient_id == patient_id)
        .order_by(EMROutcome.recorded_at.desc(), EMROutcome.id.desc())
        .first()
    )
    latest_lab = (
        db.query(EMRLabOrder)
        .filter(EMRLabOrder.patient_id == patient_id)
        .order_by(EMRLabOrder.ordered_at.desc(), EMRLabOrder.id.desc())
        .first()
    )
    return {
        "patient_id": patient.id,
        "patient_name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "latest_case": {
            "diagnosis": latest_case.diagnosis if latest_case else "",
            "symptoms": latest_case.symptoms if latest_case else "",
            "notes": latest_case.notes if latest_case else "",
            "followup_date": _safe_date(latest_case.followup_date) if latest_case else None,
            "followup_notes": latest_case.followup_notes if latest_case else "",
        },
        "latest_consultation": {
            "title": latest_consultation.title if latest_consultation else "",
            "status": latest_consultation.status if latest_consultation else "",
            "chief_complaint": latest_consultation.chief_complaint if latest_consultation else "",
            "treatment_plan": latest_consultation.treatment_plan if latest_consultation else "",
            "followup_date": _safe_date(latest_consultation.followup_date) if latest_consultation else None,
        },
        "latest_outcome": {
            "improvement_status": latest_outcome.improvement_status if latest_outcome else "",
            "symptom_score": latest_outcome.symptom_score if latest_outcome else None,
            "notes": latest_outcome.notes if latest_outcome else "",
        },
        "latest_emr_outcome": {
            "parameter_name": latest_emr_outcome.parameter_name if latest_emr_outcome else "",
            "improvement_percentage": latest_emr_outcome.improvement_percentage if latest_emr_outcome else None,
            "rating": latest_emr_outcome.rating if latest_emr_outcome else None,
            "notes": latest_emr_outcome.notes if latest_emr_outcome else "",
        },
        "latest_lab": {
            "status": latest_lab.status if latest_lab else "",
            "priority": latest_lab.priority if latest_lab else "",
            "lab_name": latest_lab.lab_name if latest_lab else "",
        },
    }


ai_dashboard = AIDashboardIntelligence()
