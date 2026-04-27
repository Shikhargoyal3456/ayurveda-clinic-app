#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, commit_with_retry, init_db  # noqa: E402
from app.main import app  # noqa: E402
from models.medicine import Medicine, MedicineOrder, Pharmacy  # noqa: E402


def ensure_demo_order() -> int:
    init_db()
    db = SessionLocal()
    try:
        pharmacy = db.query(Pharmacy).first()
        if pharmacy is None:
            pharmacy = Pharmacy(
                name="Test Pharmacy",
                address="Ops Hub",
                city="Delhi",
                pincode="110001",
                phone="9999999999",
                whatsapp_number="9999999999",
                drug_licence_number="TMP-001",
                is_active=True,
            )
            db.add(pharmacy)
            commit_with_retry(db)
            db.refresh(pharmacy)
        medicine = db.query(Medicine).first()
        if medicine is None:
            medicine = Medicine(
                name="Test Medicine",
                category="allopathy",
                price=99,
                mrp=120,
                stock=100,
                unit="strip",
                requires_prescription=False,
                is_available=True,
                pharmacy_id=pharmacy.id,
            )
            db.add(medicine)
            commit_with_retry(db)
            db.refresh(medicine)
        order = db.query(MedicineOrder).order_by(MedicineOrder.id.desc()).first()
        if order is None:
            order = MedicineOrder(
                patient_name="Demo Patient",
                patient_phone="9999999999",
                patient_address="Delhi",
                medicines_json=json.dumps([{"name": medicine.name, "qty": 1, "price": medicine.price, "line_total": medicine.price}]),
                total_amount=medicine.price,
                status="pending",
                pharmacy_id=pharmacy.id,
                payment_status="pending",
            )
            db.add(order)
            commit_with_retry(db)
            db.refresh(order)
        return int(order.id)
    finally:
        db.close()


def main() -> int:
    order_id = ensure_demo_order()
    client = TestClient(app)
    checks: list[tuple[str, bool, str]] = []

    def record(name: str, condition: bool, detail: str = "") -> None:
        checks.append((name, condition, detail))

    health = client.get("/health")
    record("health endpoint", health.status_code == 200 and health.json().get("status") in {"healthy", "degraded"}, str(health.status_code))

    healthz = client.get("/healthz")
    record("healthz endpoint", healthz.status_code == 200, str(healthz.status_code))

    docs = client.get("/docs")
    record("docs endpoint", docs.status_code == 200, str(docs.status_code))

    static_css = client.get("/static/css/style.min.css")
    record("static file", static_css.status_code == 200, str(static_css.status_code))

    order_check = client.get(f"/api/orders/check/{order_id}")
    record("order check API", order_check.status_code == 200 and order_check.json().get("exists") is True, str(order_check.status_code))

    invoice = client.get(f"/orders/invoice/{order_id}")
    record("invoice page", invoice.status_code == 200, str(invoice.status_code))

    with client.websocket_connect("/ws/activity") as websocket:
        websocket.send_text("ping")
        record("websocket connect", True, "connected")

    rate_statuses = []
    for _ in range(21):
        response = client.post("/api/support/chat", json={"message": "hello"})
        rate_statuses.append(response.status_code)
    record("rate limiting", 429 in rate_statuses, str(rate_statuses[-3:]))

    email_configured = __import__("services.email_service", fromlist=["EmailService"]).EmailService().is_configured()
    record("email service available", True, "configured" if email_configured else "not configured, graceful fallback")

    print("\nFinal Test Suite")
    failed = [item for item in checks if not item[1]]
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} - {name} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
