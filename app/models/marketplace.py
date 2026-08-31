from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PharmacyStore(Base):
    __tablename__ = "pharmacy_stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_pharmacy_id: Mapped[int | None] = mapped_column(ForeignKey("pharmacies.id"), nullable=True, index=True)
    store_name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    opening_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    closing_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    delivery_radius_km: Mapped[int] = mapped_column(Integer, default=5)
    minimum_order_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    delivery_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    rating: Mapped[float] = mapped_column(Numeric(3, 1), default=0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class LabStore(Base):
    __tablename__ = "lab_stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lab_name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    accreditation: Mapped[str] = mapped_column(String(100), default="")
    is_home_collection_available: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float] = mapped_column(Numeric(3, 1), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DeliveryPartner(Base):
    __tablename__ = "delivery_partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    vehicle_type: Mapped[str] = mapped_column(String(50), default="bike")
    current_latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    rating: Mapped[float] = mapped_column(Numeric(3, 1), default=5)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OrderDelivery(Base):
    __tablename__ = "order_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, index=True)
    pharmacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    delivery_partner_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_partners.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="assigned", index=True)
    pickup_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    live_latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    live_longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tracking_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
