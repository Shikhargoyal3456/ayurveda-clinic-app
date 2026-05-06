from __future__ import annotations


def notification_center(role: str) -> list[dict[str, str]]:
    shared = [
        {"title": "Payment confirmation", "body": "Recent payment updates are synced across all portals.", "level": "success"},
        {"title": "Delivery tracking", "body": "Live route refresh is active for current medicine orders.", "level": "info"},
    ]
    role_specific = {
        "patient": [
            {"title": "Refill reminder", "body": "Ashwagandha refill due in 2 days.", "level": "warning"},
            {"title": "Prescription updated", "body": "Your latest doctor prescription is ready to reorder.", "level": "info"},
        ],
        "pharmacy": [
            {"title": "Stock alert", "body": "3 SKUs need replenishment before evening peak.", "level": "warning"},
            {"title": "Queue update", "body": "Two paid orders are waiting for preparation.", "level": "info"},
        ],
        "doctor": [
            {"title": "Appointment reminder", "body": "Your next consult begins in 20 minutes.", "level": "info"},
            {"title": "Prescription request", "body": "A returning patient requested a refill review.", "level": "warning"},
        ],
        "lab": [
            {"title": "Home collection", "body": "Morning collection slot is nearly full.", "level": "warning"},
            {"title": "Report ready", "body": "Three reports are waiting for publishing.", "level": "info"},
        ],
        "partner": [
            {"title": "Assignment ready", "body": "A nearby medicine delivery is available now.", "level": "info"},
            {"title": "Payout update", "body": "Yesterday's earnings have been settled.", "level": "success"},
        ],
    }
    return role_specific.get(role, []) + shared
