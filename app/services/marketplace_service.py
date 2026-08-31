from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

from app.database import SessionLocal, commit_with_retry
from app.models import Appointment, Doctor, Patient
from models.ai_features import AIPrescriptionScan
from models.emr import EMRLabOrder
from models.marketplace import DeliveryPartner, LabStore, OrderDelivery, PharmacyStore
from models.medicine import Medicine, MedicineOrder, Pharmacy
from services.superapp_service import get_dashboard_payload


def ensure_marketplace_seed_data() -> dict[str, int]:
    db = SessionLocal()
    created = {"pharmacy_stores": 0, "lab_stores": 0, "delivery_partners": 0}
    try:
        if db.query(PharmacyStore).count() == 0:
            for pharmacy in db.query(Pharmacy).order_by(Pharmacy.id.asc()).limit(5).all():
                db.add(
                    PharmacyStore(
                        owner_id=pharmacy.id,
                        source_pharmacy_id=pharmacy.id,
                        store_name=pharmacy.name,
                        address=pharmacy.address,
                        latitude=pharmacy.lat,
                        longitude=pharmacy.lng,
                        phone=pharmacy.phone,
                        email=f"{pharmacy.name.lower().replace(' ', '.')}@kashai.test",
                        gst_number=f"GST{pharmacy.id:05d}",
                        is_open=True,
                        delivery_radius_km=7,
                        minimum_order_amount=199,
                        delivery_fee=49,
                        rating=4.5,
                        total_orders=12 + pharmacy.id,
                    )
                )
                created["pharmacy_stores"] += 1
        if db.query(LabStore).count() == 0:
            sample_labs = [
                ("Kash Diagnostics Central", "Sector 14, Gurugram", "28.4595", "77.0266", "NABL"),
                ("AyurLab Home Collection", "DLF Phase 1, Gurugram", "28.4729", "77.0820", "ISO"),
            ]
            for index, (name, address, lat, lng, accreditation) in enumerate(sample_labs, start=1):
                db.add(
                    LabStore(
                        owner_id=index,
                        lab_name=name,
                        address=address,
                        latitude=lat,
                        longitude=lng,
                        phone="9999999999",
                        email=f"lab{index}@kashai.test",
                        accreditation=accreditation,
                        is_home_collection_available=True,
                        rating=4.6,
                    )
                )
                created["lab_stores"] += 1
        if db.query(DeliveryPartner).count() == 0:
            partners = [
                ("Ravi Rider", "9000000001", "bike", "28.4700", "77.0300", 4.9),
                ("Meera Express", "9000000002", "scooter", "28.4650", "77.0400", 4.8),
                ("Health Fleet 3", "9000000003", "bike", "28.4550", "77.0200", 4.7),
            ]
            for name, phone, vehicle, lat, lng, rating in partners:
                db.add(
                    DeliveryPartner(
                        name=name,
                        phone=phone,
                        vehicle_type=vehicle,
                        current_latitude=lat,
                        current_longitude=lng,
                        is_available=True,
                        rating=rating,
                        total_deliveries=20,
                    )
                )
                created["delivery_partners"] += 1
        commit_with_retry(db)
        return created
    finally:
        db.close()


def patient_portal_payload(user_id: str = "guest") -> dict[str, Any]:
    base = get_dashboard_payload(user_id)
    db = SessionLocal()
    try:
        stores = db.query(PharmacyStore).order_by(PharmacyStore.rating.desc()).limit(6).all()
        patient = db.query(Patient).order_by(Patient.created_at.desc()).first()
        appointments = db.query(Appointment).order_by(Appointment.date.asc()).limit(5).all()
        deliveries = db.query(OrderDelivery).order_by(OrderDelivery.created_at.desc()).limit(5).all()
        return {
            "patient": {
                "name": patient.name if patient else "Guest Patient",
                "id": patient.id if patient else 0,
            },
            "health_score": base.get("health_score", 60),
            "active_orders": [
                {
                    "order_id": item.order_id,
                    "status": item.status,
                    "tracking_url": item.tracking_url,
                    "delivery_fee": float(item.delivery_fee or 0),
                }
                for item in deliveries
            ],
            "nearby_pharmacies": [
                {
                    "id": store.id,
                    "name": store.store_name,
                    "rating": float(store.rating or 0),
                    "delivery_fee": float(store.delivery_fee or 0),
                    "is_open": bool(store.is_open),
                }
                for store in stores
            ],
            "appointments": [
                {"id": item.id, "date": item.date.isoformat(), "time": item.time, "status": item.status}
                for item in appointments
            ],
            "ai_insights": base.get("health_insights", []),
        }
    finally:
        db.close()


def doctor_portal_payload(doctor_id: int | None = None, doctor_user_id: int | None = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        doctor = db.get(Doctor, doctor_id) if doctor_id else db.query(Doctor).order_by(Doctor.created_at.asc()).first()
        patient_query = db.query(Patient)
        if doctor is not None:
            patient_query = patient_query.filter(Patient.doctor_id == doctor.id)
        patients = patient_query.order_by(Patient.created_at.desc()).all()

        appointment_query = db.query(Appointment)
        if doctor is not None:
            appointment_query = appointment_query.join(Patient).filter(Patient.doctor_id == doctor.id)
        appointments = appointment_query.order_by(Appointment.date.asc(), Appointment.time.asc()).all()

        prescription_query = db.query(AIPrescriptionScan)
        if doctor_user_id is not None:
            prescription_query = prescription_query.filter(AIPrescriptionScan.doctor_user_id == doctor_user_id)
        prescriptions = (
            prescription_query
            .order_by(AIPrescriptionScan.created_at.desc(), AIPrescriptionScan.id.desc())
            .limit(6)
            .all()
        )
        return {
            "doctor": {
                "id": doctor.id if doctor else 0,
                "name": doctor.full_name if doctor else "Doctor",
                "specialty": doctor.specialty if doctor else "ayurveda",
            },
            "patients": [
                {
                    "id": item.id,
                    "name": item.name,
                    "age": item.age,
                    "gender": item.gender,
                    "created_at": item.created_at,
                }
                for item in patients[:10]
            ],
            "appointments": [
                {
                    "id": item.id,
                    "date": item.date,
                    "time": item.time,
                    "status": item.status,
                    "reason": item.reason,
                    "patient_id": item.patient_id,
                    "patient_name": item.patient.name if item.patient else "Patient",
                }
                for item in appointments[:12]
            ],
            "prescriptions": [
                {
                    "id": item.id,
                    "title": item.title or f"Prescription #{item.id}",
                    "status": item.status,
                    "created_at": item.created_at,
                    "patient_name": (item.title or "").replace("E-Prescription for ", "").strip() or "Patient",
                    "medicine": (item.medicines[0].get("name", "Prescription review") if isinstance(item.medicines, list) and item.medicines else "Prescription review"),
                }
                for item in prescriptions
            ],
            "all_patients_count": len(patients),
            "all_appointments_count": len(appointments),
            "today_consults": len([item for item in appointments if item.date == date.today()]),
        }
    finally:
        db.close()


def pharmacy_owner_dashboard_payload(store_id: int | None = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        store = db.get(PharmacyStore, store_id) if store_id else db.query(PharmacyStore).order_by(PharmacyStore.rating.desc()).first()
        if store is None:
            ensure_marketplace_seed_data()
            store = db.query(PharmacyStore).order_by(PharmacyStore.id.asc()).first()
        source_pharmacy_id = int(store.source_pharmacy_id or 0) if store else 0
        orders = db.query(MedicineOrder).filter(MedicineOrder.pharmacy_id == source_pharmacy_id).order_by(MedicineOrder.created_at.desc()).limit(12).all()
        products = db.query(Medicine).filter(Medicine.pharmacy_id == source_pharmacy_id).all()
        low_stock_count = len([item for item in products if int(item.stock or 0) < 10])
        today_orders = len([item for item in orders if item.created_at.date() == date.today()])
        today_revenue = sum(int(item.total_amount or 0) for item in orders if item.created_at.date() == date.today())
        return {
            "pharmacy": store,
            "orders": orders,
            "low_stock_count": low_stock_count,
            "expiring_count": 0,
            "total_products": len(products),
            "today_orders": today_orders,
            "today_revenue": today_revenue,
            "avg_prep_time": 18,
            "rating": float(store.rating or 0) if store else 4.5,
        }
    finally:
        db.close()


def lab_owner_dashboard_payload(lab_id: int | None = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        lab = db.get(LabStore, lab_id) if lab_id else db.query(LabStore).order_by(LabStore.rating.desc()).first()
        if lab is None:
            ensure_marketplace_seed_data()
            lab = db.query(LabStore).order_by(LabStore.id.asc()).first()
        orders = db.query(EMRLabOrder).order_by(EMRLabOrder.ordered_at.desc()).limit(12).all()
        today_appointments = [item for item in orders if item.ordered_at.date() == date.today()]
        return {
            "lab": lab,
            "today_appointments_count": len(today_appointments),
            "today_appointments": orders,
            "active_tests": len(orders),
            "todays_bookings": len(today_appointments),
            "home_collections": [item for item in orders if item.status != "completed"][:5],
        }
    finally:
        db.close()


def marketplace_nearby_shops() -> dict[str, Any]:
    db = SessionLocal()
    try:
        pharmacies = db.query(PharmacyStore).order_by(PharmacyStore.rating.desc()).limit(8).all()
        labs = db.query(LabStore).order_by(LabStore.rating.desc()).limit(8).all()
        return {
            "pharmacies": [
                {"id": store.id, "name": store.store_name, "rating": float(store.rating or 0), "is_open": bool(store.is_open)}
                for store in pharmacies
            ],
            "labs": [
                {"id": lab.id, "name": lab.lab_name, "rating": float(lab.rating or 0), "home_collection": bool(lab.is_home_collection_available)}
                for lab in labs
            ],
        }
    finally:
        db.close()


def pharmacy_live_orders(store_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        store = db.get(PharmacyStore, store_id)
        if store is None:
            return []
        orders = db.query(MedicineOrder).filter(MedicineOrder.pharmacy_id == int(store.source_pharmacy_id or 0)).order_by(MedicineOrder.created_at.desc()).limit(20).all()
        def prescription_meta(order: MedicineOrder) -> tuple[bool, int | None]:
            try:
                items = json.loads(order.medicines_json or "[]")
            except json.JSONDecodeError:
                return False, None
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and str(item.get("source", "")).strip().lower() == "prescription":
                    value = int(item.get("prescription_id", 0) or 0)
                    return value > 0, value or None
            return False, None
        return [
            {
                "id": order.id,
                "patient_name": order.patient_name,
                "status": order.status,
                "payment_status": order.payment_status,
                "total_amount": int(order.total_amount or 0),
                "created_at": order.created_at.isoformat(),
                "customer_rating": 5 if order.payment_status == "paid" else 4,
                "auto_accept_enabled": True,
                "has_prescription": prescription_meta(order)[0],
                "prescription_id": prescription_meta(order)[1],
            }
            for order in orders
        ]
    finally:
        db.close()


def pharmacy_inventory_snapshot(store_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        store = db.get(PharmacyStore, store_id)
        if store is None:
            return []
        items = db.query(Medicine).filter(Medicine.pharmacy_id == int(store.source_pharmacy_id or 0)).order_by(Medicine.name.asc()).all()
        return [
            {
                "id": item.id,
                "name": item.name,
                "stock": int(item.stock or 0),
                "price": int(item.price or 0),
                "is_available": bool(item.is_available),
            }
            for item in items
        ]
    finally:
        db.close()
