from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationItem:
    name: str
    icon: str
    url: str
    group: str = "Workspace"
    description: str = ""


NAVIGATION: dict[str, list[NavigationItem]] = {
    "patient": [
        NavigationItem("Home", "house", "/patient", "Patient Care", "Your patient dashboard"),
        NavigationItem("Search Medicines", "capsules", "/order-medicines", "Patient Care", "Search and reorder medicines"),
        NavigationItem("Orders", "box", "/orders", "Patient Care", "Track active deliveries"),
        NavigationItem("Health", "heart-pulse", "/my-health", "Patient Care", "Prescriptions and refills"),
    ],
    "pharmacy": [
        NavigationItem("Dashboard", "chart-line", "/pharmacy", "Pharmacy Ops", "Order and earnings overview"),
        NavigationItem("Orders", "clipboard-list", "/pharmacy#live-orders", "Pharmacy Ops", "Live medicine queue"),
        NavigationItem("Inventory", "boxes-stacked", "/portal/pharmacy/add-medicine", "Pharmacy Ops", "Manage medicines and stock"),
        NavigationItem("Earnings", "wallet", "/pharmacy", "Pharmacy Ops", "Daily performance and payout view"),
    ],
    "doctor": [
        NavigationItem("Dashboard", "stethoscope", "/doctor/dashboard", "Patient Care", "Today's clinic overview"),
        NavigationItem("Appointments", "calendar-days", "/appointments", "Patient Care", "Scheduled consultations"),
        NavigationItem("Patients", "users", "/emr/patient-registry", "Patient Care", "Registry and active patient queue"),
        NavigationItem("AI Scribe", "microphone-lines", "/emr/ambient-scribe", "Clinical Tools", "Listen to the visit and draft the EMR automatically"),
        NavigationItem("Prescriptions", "file-waveform", "/doctor/dashboard#prescription-studio", "Clinical Tools", "Review and issue prescriptions"),
    ],
    "admin": [
        NavigationItem("Overview", "chart-pie", "/admin", "Admin Ops", "Admin overview dashboard"),
        NavigationItem("Users", "users-gear", "/admin/users", "Admin Ops", "User management"),
        NavigationItem("Orders", "box", "/admin/orders", "Admin Ops", "Recent order oversight"),
    ],
    "lab": [
        NavigationItem("Dashboard", "flask-vial", "/lab", "Lab Ops", "Bookings and backlog overview"),
        NavigationItem("Bookings", "calendar-check", "/lab#today-bookings", "Lab Ops", "Today's test schedule"),
        NavigationItem("Reports", "file-medical", "/lab#reports", "Lab Ops", "Upload and manage reports"),
        NavigationItem("Collections", "truck-medical", "/lab#collections", "Home Collection", "Pickup queue"),
        NavigationItem("Analytics", "chart-line", "/lab#analytics", "Performance", "Operational insights"),
    ],
    "partner": [
        NavigationItem("Dashboard", "motorcycle", "/delivery", "Delivery Ops", "Current shift overview"),
        NavigationItem("Assignments", "route", "/delivery#assignments", "Delivery Ops", "Open delivery jobs"),
        NavigationItem("Earnings", "wallet", "/delivery#earnings", "Delivery Ops", "Today's payout summary"),
        NavigationItem("Tracking", "location-dot", "/delivery#tracking", "Delivery Ops", "Routes and live map"),
        NavigationItem("Availability", "toggle-on", "/delivery#availability", "Delivery Ops", "Current shift status"),
        NavigationItem("Support", "life-ring", "/contact", "Support", "Get help quickly"),
    ],
}


QUICK_ACTIONS: dict[str, list[dict[str, str]]] = {
    "patient": [
        {"label": "Order Medicines", "icon": "capsules", "url": "/order-medicines"},
        {"label": "Upload Rx", "icon": "camera", "url": "/order-medicines?tab=upload"},
        {"label": "Track Orders", "icon": "box", "url": "/orders"},
    ],
    "pharmacy": [
        {"label": "Orders", "icon": "clipboard-check", "url": "/pharmacy#live-orders"},
        {"label": "Inventory", "icon": "plus", "url": "/portal/pharmacy/add-medicine"},
        {"label": "Earnings", "icon": "wallet", "url": "/pharmacy"},
    ],
    "doctor": [
        {"label": "Today's Appointments", "icon": "calendar-days", "url": "/appointments"},
        {"label": "AI Scribe", "icon": "microphone-lines", "url": "/emr/ambient-scribe"},
        {"label": "Write Rx", "icon": "pen", "url": "/doctor/dashboard#prescription-studio"},
        {"label": "Patients", "icon": "users-viewfinder", "url": "/emr/patient-registry"},
    ],
    "lab": [
        {"label": "Add Slot", "icon": "clock", "url": "/lab#today-bookings"},
        {"label": "Assign Pickup", "icon": "truck", "url": "/lab#collections"},
        {"label": "Upload Report", "icon": "file-arrow-up", "url": "/lab#reports"},
    ],
    "partner": [
        {"label": "Go Online", "icon": "toggle-on", "url": "/delivery#availability"},
        {"label": "Open Route", "icon": "route", "url": "/delivery#tracking"},
        {"label": "View Payouts", "icon": "wallet", "url": "/delivery#earnings"},
    ],
}


def doctor_dashboard_url(doctor_type: str | None = None) -> str:
    return {
        "ayurveda": "/doctor/ayurveda/dashboard",
        "modern": "/doctor/modern/dashboard",
        "homeopathy": "/doctor/homeopathy/dashboard",
        "physiotherapy": "/doctor/physiotherapy/dashboard",
        "dentistry": "/doctor/dentistry/dashboard",
        "integrated": "/doctor/integrated/dashboard",
    }.get((doctor_type or "").strip().lower(), "/doctor/dashboard")


def get_navigation_for_doctor(doctor_type: str | None = None) -> list[NavigationItem]:
    dashboard_url = doctor_dashboard_url(doctor_type)
    normalized = (doctor_type or "").strip().lower()
    if normalized == "ayurveda":
        return [
            NavigationItem("Dashboard", "leaf", dashboard_url, "Patient Care", "Ayurveda clinic overview"),
            NavigationItem("Samhita AI", "book-open", "/ai-analyzer", "Clinical Tools", "Ask classical-text grounded questions"),
            NavigationItem("Patients", "users", "/emr/patient-registry", "Patient Care", "Registry and active patient queue"),
            NavigationItem("Prescriptions", "file-waveform", "/doctor/dashboard#prescription-studio", "Clinical Tools", "Review and issue prescriptions"),
            NavigationItem("Panchakarma", "spa", "/emr/clinical-decisions", "Ayurveda Care", "Plan Ayurveda procedures and decisions"),
            NavigationItem("Telemedicine", "video", "/telemedicine/book", "Patient Care", "Consult remotely"),
        ]
    if normalized == "modern":
        return [
            NavigationItem("Dashboard", "stethoscope", dashboard_url, "Patient Care", "Modern medicine overview"),
            NavigationItem("Medical AI", "microscope", "/ai-analyzer", "Clinical Tools", "Evidence-based assistant"),
            NavigationItem("Patients", "users", "/emr/patient-registry", "Patient Care", "Registry and active patient queue"),
            NavigationItem("Prescriptions", "file-waveform", "/doctor/dashboard#prescription-studio", "Clinical Tools", "Review and issue prescriptions"),
            NavigationItem("Labs", "flask", "/emr/lab-dashboard", "Clinical Tools", "Order and review labs"),
            NavigationItem("Telemedicine", "video", "/telemedicine/book", "Patient Care", "Consult remotely"),
        ]
    base_items = list(NAVIGATION.get("doctor", []))
    if base_items:
        base_items[0] = NavigationItem(base_items[0].name, base_items[0].icon, dashboard_url, base_items[0].group, base_items[0].description)
    return base_items


def get_quick_actions_for_doctor(doctor_type: str | None = None) -> list[dict[str, str]]:
    dashboard_url = doctor_dashboard_url(doctor_type)
    normalized = (doctor_type or "").strip().lower()
    if normalized == "ayurveda":
        return [
            {"label": "Samhita AI", "icon": "book", "url": "/ai-analyzer"},
            {"label": "AI Scribe", "icon": "microphone-lines", "url": "/emr/ambient-scribe"},
            {"label": "Write Rx", "icon": "pen", "url": f"{dashboard_url}#prescription-studio"},
            {"label": "Patients", "icon": "users-viewfinder", "url": "/emr/patient-registry"},
        ]
    if normalized == "modern":
        return [
            {"label": "Medical AI", "icon": "microscope", "url": "/ai-analyzer"},
            {"label": "AI Scribe", "icon": "microphone-lines", "url": "/emr/ambient-scribe"},
            {"label": "Write Rx", "icon": "pen", "url": f"{dashboard_url}#prescription-studio"},
            {"label": "Labs", "icon": "flask", "url": "/emr/lab-dashboard"},
        ]
    return list(QUICK_ACTIONS.get("doctor", []))
