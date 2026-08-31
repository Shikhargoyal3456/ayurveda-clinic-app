from __future__ import annotations

from datetime import datetime

from app.models import Doctor, Patient, PatientQuery, PendingReview
from services.email_service import EmailService, send_email
from services.whatsapp import build_whatsapp_link


email_service = EmailService()


def _doctor_email(doctor: Doctor) -> str:
    username = str(doctor.username or "").strip()
    return username if "@" in username else ""


def _severity_label(severity: str) -> str:
    normalized = str(severity or "normal").strip().lower()
    return normalized.upper() if normalized in {"emergency", "urgent", "normal"} else "NORMAL"


def _doctor_display_name(doctor: Doctor) -> str:
    return doctor.full_name or doctor.username or "Doctor"


def doctor_alert_email_html(doctor: Doctor, patient: Patient, query: PatientQuery) -> str:
    patient_phone = patient.phone or "Not available"
    patient_whatsapp = build_whatsapp_link(patient.phone or "", f"Dr. {_doctor_email(doctor) or doctor.full_name or doctor.username} is reviewing your message.")
    created_at = (query.created_at or datetime.utcnow()).strftime("%d %b %Y, %I:%M %p")
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">
        <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden;">
            <div style="background:{'#991b1b' if query.severity == 'emergency' else '#b45309'};color:#ffffff;padding:20px 24px;">
                <h2 style="margin:0;">Patient Alert: {_severity_label(query.severity)}</h2>
                <p style="margin:8px 0 0;">Kash AI flagged a patient message that may need timely doctor review.</p>
            </div>
            <div style="padding:24px;">
                <p><strong>Doctor:</strong> {doctor.full_name or doctor.username}</p>
                <p><strong>Patient:</strong> {patient.name}</p>
                <p><strong>Phone:</strong> {patient_phone}</p>
                <p><strong>Received:</strong> {created_at}</p>
                <div style="background:#fff7ed;border-radius:14px;padding:14px;margin:18px 0;">
                    <strong>Patient message</strong>
                    <p style="margin:8px 0 0;">{query.query_text}</p>
                </div>
                <div style="background:#f8fafc;border-radius:14px;padding:14px;margin:18px 0;">
                    <strong>AI reply</strong>
                    <p style="margin:8px 0 0;">{query.ai_response}</p>
                </div>
                <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:20px;">
                    <a href="tel:{patient_phone}" style="background:#111827;color:#fff;padding:12px 18px;border-radius:999px;text-decoration:none;">Call patient</a>
                    <a href="{patient_whatsapp or '#'}" style="background:#25D366;color:#fff;padding:12px 18px;border-radius:999px;text-decoration:none;">WhatsApp patient</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


async def notify_doctor_of_alert(doctor: Doctor, patient: Patient, query: PatientQuery) -> dict[str, object]:
    recipient = _doctor_email(doctor)
    if not recipient:
        return {"success": False, "reason": "missing_doctor_email"}
    return await email_service.send_html_email(
        to_email=recipient,
        subject=f"Kash AI {_severity_label(query.severity)} patient alert - {patient.name}",
        html_body=doctor_alert_email_html(doctor, patient, query),
        text_body=f"Patient {patient.name} sent a {_severity_label(query.severity)} message: {query.query_text}",
    )


async def notify_doctor_pending_review(doctor: Doctor, patient: Patient, review: PendingReview) -> dict[str, object]:
    recipient = _doctor_email(doctor)
    if not recipient:
        return {"success": False, "reason": "missing_doctor_email"}

    dashboard_url = "http://localhost:8000/dashboard"
    subject = f"Pending AI response review for {patient.name}"
    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">
        <div style="max-width:680px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden;">
            <div style="background:#b45309;color:#ffffff;padding:20px 24px;">
                <h2 style="margin:0;">Doctor Review Required</h2>
                <p style="margin:8px 0 0;">Kash AI drafted a patient response and is waiting for your approval.</p>
            </div>
            <div style="padding:24px;">
                <p><strong>Doctor:</strong> {_doctor_display_name(doctor)}</p>
                <p><strong>Patient:</strong> {patient.name}</p>
                <p><strong>Received:</strong> {(review.created_at or datetime.utcnow()).strftime("%d %b %Y, %I:%M %p")}</p>
                <div style="background:#f8fafc;border-radius:14px;padding:14px;margin:18px 0;">
                    <strong>Patient asked</strong>
                    <p style="margin:8px 0 0;">{review.question}</p>
                </div>
                <div style="background:#eff6ff;border-radius:14px;padding:14px;margin:18px 0;">
                    <strong>AI draft</strong>
                    <p style="margin:8px 0 0;white-space:pre-wrap;">{review.ai_suggestion}</p>
                </div>
                <p style="margin:18px 0 0;color:#b45309;font-weight:700;">AI assists. Doctor decides. Nothing is sent to the patient until you approve it.</p>
                <div style="margin-top:20px;">
                    <a href="{dashboard_url}" style="background:#111827;color:#fff;padding:12px 18px;border-radius:999px;text-decoration:none;display:inline-block;">Review in Dashboard</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return await email_service.send_html_email(
        to_email=recipient,
        subject=subject,
        html_body=html,
        text_body=f"Patient {patient.name} asked: {review.question}\nAI draft ready for review in the dashboard.",
    )


async def send_pending_review_reminder(doctor: Doctor, patient: Patient, review: PendingReview) -> dict[str, object]:
    recipient = _doctor_email(doctor)
    if not recipient:
        return {"success": False, "reason": "missing_doctor_email"}
    body = (
        f"Reminder: Kash AI still has a pending patient response waiting for review.\n\n"
        f"Patient: {patient.name}\n"
        f"Question: {review.question}\n\n"
        f"Open the dashboard to approve, edit, or reject the draft before anything is sent."
    )
    return await send_email(
        recipient,
        f"Reminder: pending AI review for {patient.name}",
        body,
        is_html=False,
    )
