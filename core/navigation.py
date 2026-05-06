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
        NavigationItem("Medicines", "capsules", "/order-medicines", "Patient Care", "Search and reorder medicines"),
        NavigationItem("Orders", "box", "/orders", "Patient Care", "Track active deliveries"),
        NavigationItem("Health", "heart-pulse", "/my-health", "Patient Care", "Prescriptions and refills"),
        NavigationItem("Consult", "user-doctor", "/telemedicine/book", "Support", "Book a doctor consult"),
    ],
    "pharmacy": [
        NavigationItem("Dashboard", "chart-line", "/pharmacy", "Pharmacy Ops", "Order and earnings overview"),
        NavigationItem("Orders", "clipboard-list", "/pharmacy#live-orders", "Pharmacy Ops", "Live medicine queue"),
        NavigationItem("Inventory", "boxes-stacked", "/portal/pharmacy/add-medicine", "Inventory", "Manage medicines and stock"),
        NavigationItem("Alerts", "triangle-exclamation", "/portal/pharmacy/stock-alerts", "Inventory", "Low-stock issues"),
        NavigationItem("Expiry", "calendar-xmark", "/portal/pharmacy/expiry-tracker", "Inventory", "Expiry tracking"),
    ],
    "doctor": [
        NavigationItem("Dashboard", "stethoscope", "/doctor/dashboard", "Patient Care", "Today's clinic overview"),
        NavigationItem("Appointments", "calendar-days", "/appointments", "Patient Care", "Scheduled consultations"),
        NavigationItem("Patients", "users", "/emr/patient-registry", "Patient Care", "Registry and queue"),
        NavigationItem("Prescriptions", "file-waveform", "/doctor/dashboard#prescription-studio", "Clinical Tools", "Review and issue prescriptions"),
        NavigationItem("Calls", "video", "/telemedicine/book", "Clinical Tools", "Video consultations"),
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
        {"label": "Quick Reorder", "icon": "rotate-right", "url": "/order-medicines"},
        {"label": "One-click Refill", "icon": "capsules", "url": "/my-health"},
        {"label": "Upload Rx", "icon": "camera", "url": "/order-medicines?tab=upload"},
    ],
    "pharmacy": [
        {"label": "Accept Queue", "icon": "clipboard-check", "url": "/portal/pharmacy#live-orders"},
        {"label": "Add Medicine", "icon": "plus", "url": "/portal/pharmacy/add-medicine"},
        {"label": "Bulk Upload", "icon": "upload", "url": "/portal/pharmacy/bulk-upload"},
    ],
    "doctor": [
        {"label": "Start Consult", "icon": "video", "url": "/telemedicine/book"},
        {"label": "Write Rx", "icon": "pen", "url": "/doctor/dashboard#prescription-studio"},
        {"label": "Patient Queue", "icon": "users-viewfinder", "url": "/doctor/dashboard#patient-queue"},
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
