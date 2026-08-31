from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.audit import write_audit_event
from app.auth import get_current_doctor, verify_csrf
from app.database import commit_with_retry, get_db
from app.models import Doctor, Patient, PendingReview
from services.doctor_notifier import send_pending_review_reminder
from services.email_service import send_email
from services.whatsapp import build_whatsapp_link


router = APIRouter(prefix="/api/doctor", tags=["Doctor Review"])
REVIEW_REMINDER_AFTER = timedelta(hours=4)


def get_time_ago(dt: datetime | None) -> str:
    if dt is None:
        return "just now"
    now = datetime.now(timezone.utc)
    value = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    diff = max(timedelta(0), now - value)
    if diff < timedelta(minutes=1):
        seconds = max(1, int(diff.total_seconds()))
        return f"{seconds} second{'s' if seconds != 1 else ''} ago"
    if diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if diff < timedelta(days=1):
        hours = int(diff.total_seconds() // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = diff.days
    return f"{days} day{'s' if days != 1 else ''} ago"


async def _send_review_reminders_if_due(db: Session, doctor: Doctor, reviews: list[PendingReview]) -> None:
    now = datetime.now(timezone.utc)
    for review in reviews:
        created_at = review.created_at if review.created_at and review.created_at.tzinfo else (review.created_at.replace(tzinfo=timezone.utc) if review.created_at else now)
        if review.status != "pending":
            continue
        if now - created_at < REVIEW_REMINDER_AFTER:
            continue
        reminder_sent_at = review.reminder_sent_at
        if reminder_sent_at:
            reminder_value = reminder_sent_at if reminder_sent_at.tzinfo else reminder_sent_at.replace(tzinfo=timezone.utc)
            if now - reminder_value < REVIEW_REMINDER_AFTER:
                continue
        patient = db.get(Patient, review.patient_id)
        if patient is None:
            continue
        result = await send_pending_review_reminder(doctor, patient, review)
        if result.get("success"):
            review.reminder_sent_at = now
            review.reminder_count = int(review.reminder_count or 0) + 1
    commit_with_retry(db)


@router.get("/pending-reviews")
async def get_pending_reviews(
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
):
    reviews = (
        db.query(PendingReview)
        .filter(PendingReview.doctor_id == doctor.id, PendingReview.status == "pending")
        .order_by(PendingReview.created_at.desc(), PendingReview.id.desc())
        .all()
    )
    await _send_review_reminders_if_due(db, doctor, reviews)
    payload = []
    for review in reviews:
        patient = db.get(Patient, review.patient_id)
        if patient is None:
            continue
        payload.append(
            {
                "id": review.id,
                "patient_id": review.patient_id,
                "patient_name": patient.name,
                "question": review.question,
                "ai_suggestion": review.ai_suggestion,
                "status": review.status,
                "time_ago": get_time_ago(review.created_at),
                "created_at": review.created_at.isoformat() if review.created_at else None,
                "severity": "",
            }
        )
    return JSONResponse(payload)


@router.post("/approve-review/{review_id}")
async def approve_review(
    review_id: int,
    request: Request,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    payload = payload or {}
    review = (
        db.query(PendingReview)
        .filter(PendingReview.id == review_id, PendingReview.doctor_id == doctor.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    patient = db.get(Patient, review.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    final_response = str(payload.get("edited_response") or review.ai_suggestion or "").strip()
    if not final_response:
        raise HTTPException(status_code=400, detail="Approved response cannot be empty")

    delivery_results: list[str] = []
    sent_to_patient = False
    if patient.email:
        email_result = await send_email(
            patient.email,
            f"Response from Dr. {doctor.full_name or doctor.username}",
            final_response,
            is_html=False,
        )
        if email_result.get("success"):
            sent_to_patient = True
            delivery_results.append(f"email:{patient.email}")
        else:
            delivery_results.append(f"email_failed:{email_result.get('reason') or email_result.get('error') or 'unknown'}")
    if patient.phone:
        whatsapp_link = build_whatsapp_link(patient.phone, final_response)
        if whatsapp_link:
            delivery_results.append(f"whatsapp_link:{whatsapp_link}")

    review.approved_response = final_response
    review.status = "sent" if sent_to_patient else "approved"
    review.delivery_channel = "email" if sent_to_patient else ("manual" if patient.phone else "none")
    review.delivery_notes = "\n".join(delivery_results) if delivery_results else "No delivery channel available."
    review.approved_at = datetime.now(timezone.utc)
    commit_with_retry(db)
    write_audit_event(
        "pending_review_approved",
        request,
        review_id=review.id,
        patient_id=review.patient_id,
        doctor_id=doctor.id,
        sent_to_patient=sent_to_patient,
        edited=final_response != (review.ai_suggestion or ""),
    )
    return JSONResponse(
        {
            "success": True,
            "sent_to_patient": sent_to_patient,
            "delivery_notes": review.delivery_notes,
        }
    )


@router.post("/reject-review/{review_id}")
async def reject_review(
    review_id: int,
    request: Request,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    doctor: Doctor = Depends(get_current_doctor),
    _: None = Depends(verify_csrf),
):
    payload = payload or {}
    review = (
        db.query(PendingReview)
        .filter(PendingReview.id == review_id, PendingReview.doctor_id == doctor.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    patient = db.get(Patient, review.patient_id)
    review.status = "rejected"
    review.rejection_reason = str(payload.get("reason") or "Doctor will respond manually.").strip()
    review.approved_at = datetime.now(timezone.utc)
    commit_with_retry(db)

    if patient and patient.email:
        await send_email(
            patient.email,
            f"Update from Dr. {doctor.full_name or doctor.username}",
            "Your doctor has received your message and will respond manually shortly.",
            is_html=False,
        )

    write_audit_event(
        "pending_review_rejected",
        request,
        review_id=review.id,
        patient_id=review.patient_id,
        doctor_id=doctor.id,
        reason=review.rejection_reason,
    )
    return JSONResponse({"success": True})
