from __future__ import annotations

import logging
from urllib.parse import quote


logger = logging.getLogger(__name__)


def send_whatsapp_message(phone: str, message: str) -> None:
    """Safe placeholder for future Twilio integration."""
    normalized_phone = (phone or "").strip()
    if not normalized_phone:
        logger.info("WhatsApp placeholder skipped because patient phone is unavailable.")
        return

    logger.info("WhatsApp placeholder send to=%s message=%s", normalized_phone, message.strip())


def build_whatsapp_link(phone: str, message: str) -> str:
    normalized_phone = "".join(character for character in (phone or "").strip() if character.isdigit())
    if not normalized_phone:
        return ""
    return f"https://wa.me/{normalized_phone}?text={quote((message or '').strip())}"
