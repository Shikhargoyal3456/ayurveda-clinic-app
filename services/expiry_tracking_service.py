from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.database import commit_with_retry
from models.medicine import MasterMedicine, Medicine, PharmacyInventory


class ExpiryTrackingService:
    """Track expiring medicines and apply clearance pricing."""

    def __init__(self) -> None:
        self.expiry_windows = {
            "critical": 30,
            "warning": 60,
            "notice": 90,
        }

    def get_expiry_alert_level(self, days_left: int) -> str:
        if days_left <= self.expiry_windows["critical"]:
            return "critical"
        if days_left <= self.expiry_windows["warning"]:
            return "warning"
        if days_left <= self.expiry_windows["notice"]:
            return "notice"
        return "safe"

    def calculate_clearance_discount(self, days_left: int) -> float:
        if days_left <= 7:
            return 70
        if days_left <= 15:
            return 50
        if days_left <= 30:
            return 30
        return 20

    def check_expiring_medicines(self, db: Session, pharmacy_store_id: int) -> list[dict[str, Any]]:
        today = date.today()
        warning_date = today + timedelta(days=self.expiry_windows["notice"])
        rows = (
            db.query(PharmacyInventory, Medicine, MasterMedicine)
            .outerjoin(Medicine, Medicine.id == PharmacyInventory.medicine_id)
            .outerjoin(MasterMedicine, MasterMedicine.id == PharmacyInventory.master_medicine_id)
            .filter(
                PharmacyInventory.pharmacy_store_id == pharmacy_store_id,
                PharmacyInventory.is_available.is_(True),
                PharmacyInventory.expiry_date.is_not(None),
                PharmacyInventory.expiry_date <= warning_date,
            )
            .order_by(PharmacyInventory.expiry_date.asc(), PharmacyInventory.stock.desc())
            .all()
        )

        alerts: list[dict[str, Any]] = []
        for inventory, medicine, master in rows:
            days_left = (inventory.expiry_date - today).days if inventory.expiry_date else 999
            level = self.get_expiry_alert_level(days_left)
            if level == "critical":
                self.auto_flag_clearance(db, inventory, medicine, master, days_left)
            name = medicine.name if medicine else master.name if master else "Medicine"
            alerts.append(
                {
                    "id": inventory.id,
                    "medicine_id": inventory.medicine_id,
                    "master_medicine_id": inventory.master_medicine_id,
                    "medicine_name": name,
                    "brand": medicine.brand if medicine else master.brand if master else "",
                    "expiry_date": inventory.expiry_date.isoformat() if inventory.expiry_date else None,
                    "days_left": days_left,
                    "alert_level": level,
                    "quantity": int(inventory.stock or 0),
                    "is_clearance": bool(inventory.is_clearance),
                    "clearance_price": float(inventory.clearance_price or 0) if inventory.clearance_price is not None else None,
                }
            )
        return alerts

    def auto_flag_clearance(
        self,
        db: Session,
        inventory: PharmacyInventory,
        medicine: Medicine | None,
        master: MasterMedicine | None,
        days_left: int,
    ) -> None:
        price = float(inventory.price_override or (medicine.price if medicine else master.price if master else 0) or 0)
        discount = self.calculate_clearance_discount(days_left)
        inventory.is_clearance = True
        inventory.clearance_price = round(price * ((100 - discount) / 100), 2)
        inventory.clearance_reason = "Near Expiry"
        commit_with_retry(db)

    def summary(self, alerts: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "critical_count": len([item for item in alerts if item["alert_level"] == "critical"]),
            "warning_count": len([item for item in alerts if item["alert_level"] == "warning"]),
            "notice_count": len([item for item in alerts if item["alert_level"] == "notice"]),
        }
