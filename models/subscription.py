from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionPlan(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"


class ClinicSubscription(Base):
    __tablename__ = "clinic_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True, unique=True)
    plan_id: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(SubscriptionPlan, native_enum=False, values_callable=lambda enum: [item.value for item in enum]),
        default=SubscriptionPlan.FREE,
        index=True,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, native_enum=False, values_callable=lambda enum: [item.value for item in enum]),
        default=SubscriptionStatus.TRIAL,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    trial_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    doctor_id = synonym("user_id")
    plan = synonym("plan_id")
    expires_at = synonym("current_period_end")
    doctor = relationship("Doctor")


class SubscriptionUsage(Base):
    __tablename__ = "subscription_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_subscription_usage_user_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    ai_calls_used: Mapped[int] = mapped_column(Integer, default=0)
    voice_used: Mapped[int] = mapped_column(Integer, default=0)
    patients_created: Mapped[int] = mapped_column(Integer, default=0)
    prescriptions_created: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    doctor = relationship("Doctor")


TRIAL_LENGTH_DAYS = 14


def default_trial_end_date() -> date:
    return (utc_now() + timedelta(days=TRIAL_LENGTH_DAYS)).date()
