from __future__ import annotations

import os


def _enabled(name: str) -> bool:
    try:
        return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return False


def is_supplier_enabled() -> bool:
    return _enabled("ENABLE_SUPPLIER_API")


def is_delivery_enabled() -> bool:
    return _enabled("ENABLE_DELIVERY_API")


def is_pricing_enabled() -> bool:
    return _enabled("ENABLE_SMART_PRICING")


def is_whatsapp_enabled() -> bool:
    # POLISH-8-WHATSAPP-UPDATES: Toggle external WhatsApp delivery while preserving mock/fallback mode.
    return _enabled("ENABLE_WHATSAPP_API")


def is_ai_automation_enabled() -> bool:
    raw_value = os.getenv("ENABLE_AI_AUTOMATION", "").strip().lower()
    if not raw_value:
        return True
    return raw_value in {"1", "true", "yes", "on"}


def is_telemedicine_enabled() -> bool:
    raw_value = os.getenv("ENABLE_TELEMEDICINE", "").strip().lower()
    if not raw_value:
        return True
    return raw_value in {"1", "true", "yes", "on"}
