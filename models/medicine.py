from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120), index=True)
    pincode: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(40))
    whatsapp_number: Mapped[str] = mapped_column(String(40))
    lat: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lng: Mapped[str | None] = mapped_column(String(40), nullable=True)
    drug_licence_number: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    medicines: Mapped[list["Medicine"]] = relationship(
        back_populates="pharmacy",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["MedicineOrder"]] = relationship(
        back_populates="pharmacy",
        cascade="all, delete-orphan",
    )


class MasterMedicine(Base):
    __tablename__ = "medicines_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    generic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    mrp: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    images_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    popularity_score: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    generic_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    price: Mapped[int] = mapped_column(Integer)
    mrp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(40), default="unit")
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"), index=True)
    master_medicine_id: Mapped[int | None] = mapped_column(ForeignKey("medicines_master.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    pharmacy: Mapped["Pharmacy"] = relationship(back_populates="medicines")
    stock_adjustments: Mapped[list["StockAdjustment"]] = relationship(
        back_populates="medicine",
        cascade="all, delete-orphan",
    )


class PharmacyInventory(Base):
    __tablename__ = "pharmacy_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pharmacy_store_id: Mapped[int | None] = mapped_column(ForeignKey("pharmacy_stores.id"), nullable=True, index=True)
    pharmacy_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    medicine_id: Mapped[int | None] = mapped_column(ForeignKey("medicines.id"), nullable=True, index=True)
    master_medicine_id: Mapped[int | None] = mapped_column(ForeignKey("medicines_master.id"), nullable=True, index=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    price_override: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_clearance: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    clearance_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    clearance_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MedicineRequest(Base):
    __tablename__ = "medicine_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    medicine_name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pharmacy_store_id: Mapped[int | None] = mapped_column(ForeignKey("pharmacy_stores.id"), nullable=True, index=True)
    medicine_id: Mapped[int | None] = mapped_column(ForeignKey("medicines.id"), nullable=True, index=True)
    master_medicine_id: Mapped[int | None] = mapped_column(ForeignKey("medicines_master.id"), nullable=True, index=True)
    alert_level: Mapped[str] = mapped_column(String(20), index=True)
    current_stock: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int] = mapped_column(Integer, default=0)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class MedicineOrder(Base):
    __tablename__ = "medicine_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    profile_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    patient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    patient_address: Mapped[str] = mapped_column(String(255), nullable=False)
    medicines_json: Mapped[str] = mapped_column(Text)
    total_amount: Mapped[int] = mapped_column(Integer)
    # pending, confirmed, dispatched, delivered
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"), index=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # pending, paid, failed
    payment_status: Mapped[str] = mapped_column(String(40), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notification_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    pharmacy: Mapped["Pharmacy"] = relationship(back_populates="orders")


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), index=True)
    previous_stock: Mapped[int] = mapped_column(Integer, default=0)
    new_stock: Mapped[int] = mapped_column(Integer, default=0)
    adjusted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    medicine: Mapped["Medicine"] = relationship(back_populates="stock_adjustments")
