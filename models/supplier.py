from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Supplier(Base):
    __tablename__ = "suppliers"

    # SUPPLIER-FULL-1: Persistent supplier registry for admin commerce and auto-restock.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    api_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
