from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    generic_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    price: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(40))
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"), index=True)

    pharmacy: Mapped["Pharmacy"] = relationship(back_populates="medicines")


class MedicineOrder(Base):
    __tablename__ = "medicine_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
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
