from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from core.navigation import NAVIGATION, QUICK_ACTIONS
from core.notifications import notification_center
from core.search import search_scopes_for_role
from services.marketplace_service import (
    doctor_portal_payload,
    ensure_marketplace_seed_data,
    lab_owner_dashboard_payload,
    patient_portal_payload,
    pharmacy_owner_dashboard_payload,
)


PORTAL_CARDS = [
    {"slug": "patient", "label": "Patient", "icon": "user", "description": "Track orders, prescriptions, and refills."},
    {"slug": "pharmacy", "label": "Pharmacy", "icon": "store", "description": "Manage live orders, inventory, and earnings."},
    {"slug": "doctor", "label": "Doctor", "icon": "user-doctor", "description": "Run appointments, telemedicine, and prescriptions."},
    {"slug": "lab", "label": "Lab", "icon": "flask-vial", "description": "Coordinate bookings, reports, and collections."},
    {"slug": "partner", "label": "Delivery", "icon": "motorcycle", "description": "Handle assignments, tracking, and payouts."},
]


def selector_payload() -> dict[str, Any]:
    ensure_marketplace_seed_data()
    return {
        "portal_cards": PORTAL_CARDS,
        "active_page": "portal",
        "platform_name": "Kash AI",
        "welcome_title": "Choose your experience",
        "notifications": notification_center("patient"),
        "search_scopes": search_scopes_for_role("patient"),
    }


def portal_shell_context(role: str, **extra: Any) -> dict[str, Any]:
    return {
        "portal_navigation": NAVIGATION.get(role, []),
        "quick_actions": QUICK_ACTIONS.get(role, []),
        "notifications": notification_center(role),
        "search_scopes": search_scopes_for_role(role),
        "portal_role_key": role,
        **extra,
    }


def patient_dashboard_context(user_name: str = "Guest Patient", user_id: str = "guest") -> dict[str, Any]:
    payload = patient_portal_payload(user_id)
    payload["patient"]["name"] = user_name
    payload["refill_reminders"] = [
        {"name": "Ashwagandha Gold", "when": "2 days", "action_url": "/order-medicines"},
        {"name": "Giloy Tonic", "when": "5 days", "action_url": "/order-medicines"},
    ]
    payload["recommended_medicines"] = payload.get("nearby_pharmacies", [])[:3]
    return portal_shell_context("patient", **payload)


def pharmacy_dashboard_context(store_id: int | None = None) -> dict[str, Any]:
    payload = pharmacy_owner_dashboard_payload(store_id)
    payload["stock_alerts"] = payload.get("low_stock_count", 0)
    payload["customer_rating"] = payload.get("rating", 4.5)
    payload["inventory_insights"] = [
        {"label": "Fast movers", "value": "Digestive care, immunity, pain relief"},
        {"label": "Restock window", "value": "Before 6 PM rush"},
    ]
    return portal_shell_context("pharmacy", **payload)


def doctor_dashboard_context() -> dict[str, Any]:
    payload = doctor_portal_payload()
    patients = payload.get("patients", [])
    appointments = payload.get("appointments", [])
    today = date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)

    today_appointments = [item for item in appointments if item.get("date") == today]
    yesterday_appointments = [item for item in appointments if item.get("date") == yesterday]
    new_patients_this_month = [
        item for item in patients
        if item.get("created_at") and item["created_at"].date() >= month_start
    ]
    pending_prescriptions = max(1, min(5, len(today_appointments) or len(appointments) or 1))
    completed_consultations = len([
        item for item in today_appointments
        if str(item.get("status", "")).strip().lower() in {"completed", "done", "closed"}
    ])
    upcoming_appointments = []
    for index, item in enumerate(today_appointments[:4]):
        status = str(item.get("status", "")).strip().lower()
        appointment_type = "Video" if status in {"video", "confirmed", "scheduled"} or index % 2 == 0 else "Clinic"
        upcoming_appointments.append({
            **item,
            "type": appointment_type,
        })

    online_patients = []
    waiting_patients = []
    for index, patient in enumerate(patients[:4]):
        queue_entry = {
            **patient,
            "waiting_time": 2 + (index * 3),
            "request_time": f"{5 + (index * 4)} min",
        }
        if index < 2:
            online_patients.append(queue_entry)
        else:
            waiting_patients.append(queue_entry)

    pending_rx = [
        {
            "id": patient.get("id"),
            "patient_name": patient.get("name"),
            "medicine": "Awaiting final review",
        }
        for patient in patients[:3]
    ]

    total_patients = int(payload.get("all_patients_count") or len(patients))
    today_earnings = len(today_appointments) * 450
    if today_appointments and today_earnings == 0:
        today_earnings = 450

    payload["today_date"] = today.strftime("%A, %d %b %Y")
    payload["clinic_name"] = f"{str(payload.get('doctor', {}).get('specialty', 'Integrated care')).replace('_', ' ').title()} Practice"
    payload["today_appointments"] = len(today_appointments)
    payload["total_patients"] = total_patients
    payload["pending_prescriptions"] = pending_prescriptions
    payload["today_earnings"] = today_earnings
    payload["appointments_delta"] = len(today_appointments) - len(yesterday_appointments)
    payload["patients_delta"] = len(new_patients_this_month)
    payload["prescriptions_delta"] = max(0, len(yesterday_appointments) - pending_prescriptions)
    payload["earnings_delta_percent"] = 18 if today_earnings else 0
    payload["upcoming_appointments"] = upcoming_appointments
    payload["online_patients"] = online_patients
    payload["waiting_patients"] = waiting_patients
    payload["patient_queue"] = online_patients + waiting_patients
    payload["pending_rx"] = pending_rx
    payload["prescription_requests"] = pending_prescriptions
    payload["telemedicine_calls"] = len([item for item in upcoming_appointments if item.get("type") == "Video"])
    payload["earnings_summary"] = f"Rs {today_earnings:,} today"
    payload["completed_consultations"] = completed_consultations
    payload["prescriptions_issued"] = max(0, completed_consultations - 1)
    payload["avg_wait_time"] = 6 if payload["patient_queue"] else 0
    payload["satisfaction_rate"] = 96 if total_patients else 0
    return portal_shell_context("doctor", **payload)


def lab_dashboard_context(lab_id: int | None = None) -> dict[str, Any]:
    payload = lab_owner_dashboard_payload(lab_id)
    payload["earnings_summary"] = "Rs 18,600 this week"
    payload["report_backlog"] = 4
    return portal_shell_context("lab", **payload)


def delivery_dashboard_context() -> dict[str, Any]:
    payload = {
        "partner": {"name": "Delivery Partner", "status": "Online"},
        "assignments": [
            {"order_id": 9991, "pickup": "Sector 14 Pharmacy", "drop": "DLF Phase 1", "eta": "18 min"},
            {"order_id": 9992, "pickup": "MG Road Pharmacy", "drop": "Sector 43", "eta": "26 min"},
        ],
        "earnings_today": "Rs 1,450",
        "completion_rate": "96%",
    }
    return portal_shell_context("partner", **payload)
