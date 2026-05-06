from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database import commit_with_retry
from models.medicine import MasterMedicine, Medicine, PharmacyInventory, StockAlert


class StockAlertService:
    """Automatic stock monitoring and alert persistence."""

    def __init__(self) -> None:
        self.alert_thresholds = {
            "critical": 5,
            "low": 10,
            "medium": 20,
            "reorder": 50,
        }

    def get_alert_level(self, stock: int) -> str | None:
        if stock <= self.alert_thresholds["critical"]:
            return "critical"
        if stock <= self.alert_thresholds["low"]:
            return "low"
        if stock <= self.alert_thresholds["medium"]:
            return "medium"
        return None

    def check_inventory(self, db: Session, pharmacy_store_id: int | None = None) -> list[dict[str, Any]]:
        query = (
            db.query(PharmacyInventory, Medicine, MasterMedicine)
            .outerjoin(Medicine, Medicine.id == PharmacyInventory.medicine_id)
            .outerjoin(MasterMedicine, MasterMedicine.id == PharmacyInventory.master_medicine_id)
            .filter(PharmacyInventory.is_available.is_(True))
        )
        if pharmacy_store_id is not None:
            query = query.filter(PharmacyInventory.pharmacy_store_id == pharmacy_store_id)
        rows = query.all()
        alerts: list[dict[str, Any]] = []
        for inventory, medicine, master in rows:
            level = self.get_alert_level(int(inventory.stock or 0))
            if not level:
                self._resolve_existing_alerts(db, inventory.id)
                continue
            threshold = self.alert_thresholds[level]
            alert = (
                db.query(StockAlert)
                .filter(StockAlert.pharmacy_store_id == inventory.pharmacy_store_id, StockAlert.medicine_id == inventory.medicine_id, StockAlert.is_resolved.is_(False))
                .order_by(StockAlert.created_at.desc(), StockAlert.id.desc())
                .first()
            )
            if alert is None or alert.alert_level != level or alert.current_stock != int(inventory.stock or 0):
                alert = StockAlert(
                    pharmacy_store_id=inventory.pharmacy_store_id,
                    medicine_id=inventory.medicine_id,
                    master_medicine_id=inventory.master_medicine_id,
                    alert_level=level,
                    current_stock=int(inventory.stock or 0),
                    threshold=threshold,
                    is_resolved=False,
                )
                db.add(alert)
                commit_with_retry(db)
                db.refresh(alert)
            medicine_name = medicine.name if medicine else master.name if master else "Medicine"
            brand = medicine.brand if medicine else master.brand if master else ""
            alerts.append(
                {
                    "id": alert.id,
                    "pharmacy_store_id": alert.pharmacy_store_id,
                    "medicine_id": alert.medicine_id,
                    "master_medicine_id": alert.master_medicine_id,
                    "medicine_name": medicine_name,
                    "brand": brand or "",
                    "current_stock": alert.current_stock,
                    "alert_level": alert.alert_level,
                    "threshold": alert.threshold,
                    "created_at": alert.created_at.isoformat() if alert.created_at else datetime.now(timezone.utc).isoformat(),
                }
            )
        return alerts

    def _resolve_existing_alerts(self, db: Session, inventory_id: int) -> None:
        inventory = db.get(PharmacyInventory, inventory_id)
        if inventory is None:
            return
        alerts = (
            db.query(StockAlert)
            .filter(StockAlert.pharmacy_store_id == inventory.pharmacy_store_id, StockAlert.medicine_id == inventory.medicine_id, StockAlert.is_resolved.is_(False))
            .all()
        )
        changed = False
        for alert in alerts:
            alert.is_resolved = True
            changed = True
        if changed:
            commit_with_retry(db)

    def list_alerts(self, db: Session, pharmacy_store_id: int, status: str = "open") -> list[dict[str, Any]]:
        self.check_inventory(db, pharmacy_store_id=pharmacy_store_id)
        query = (
            db.query(StockAlert, Medicine, MasterMedicine)
            .outerjoin(Medicine, Medicine.id == StockAlert.medicine_id)
            .outerjoin(MasterMedicine, MasterMedicine.id == StockAlert.master_medicine_id)
            .filter(StockAlert.pharmacy_store_id == pharmacy_store_id)
            .order_by(StockAlert.is_resolved.asc(), StockAlert.created_at.desc(), StockAlert.id.desc())
        )
        if status == "open":
            query = query.filter(StockAlert.is_resolved.is_(False))
        elif status == "resolved":
            query = query.filter(StockAlert.is_resolved.is_(True))
        rows = query.limit(200).all()
        payload: list[dict[str, Any]] = []
        for alert, medicine, master in rows:
            payload.append(
                {
                    "id": alert.id,
                    "pharmacy_store_id": alert.pharmacy_store_id,
                    "medicine_id": alert.medicine_id,
                    "master_medicine_id": alert.master_medicine_id,
                    "medicine_name": medicine.name if medicine else master.name if master else "Medicine",
                    "brand": medicine.brand if medicine else master.brand if master else "",
                    "current_stock": alert.current_stock,
                    "alert_level": alert.alert_level,
                    "threshold": alert.threshold,
                    "is_resolved": bool(alert.is_resolved),
                    "created_at": alert.created_at.isoformat() if alert.created_at else None,
                }
            )
        return payload

    def mark_resolved(self, db: Session, alert_id: int, pharmacy_store_id: int) -> StockAlert | None:
        alert = db.get(StockAlert, alert_id)
        if alert is None or alert.pharmacy_store_id != pharmacy_store_id:
            return None
        alert.is_resolved = True
        commit_with_retry(db)
        db.refresh(alert)
        return alert
