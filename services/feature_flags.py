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
