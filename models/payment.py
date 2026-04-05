from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="paid", index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    payment_method: Mapped[str] = mapped_column(
        String(20), default="manual"
    )

    patient = relationship("Patient")
