from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from app.config import settings
from services.feature_flags import is_whatsapp_enabled


logger = logging.getLogger(__name__)


def _normalized_phone(phone: str) -> str:
    digits = "".join(character for character in (phone or "").strip() if character.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    return digits


def _meta_whatsapp_config() -> dict[str, str]:
    return {
        "access_token": settings.whatsapp_access_token,
        "phone_number_id": settings.whatsapp_phone_number_id,
        "api_version": settings.whatsapp_api_version,
        "template_name": settings.whatsapp_template_name,
        "template_language_code": settings.whatsapp_template_language_code,
    }


def whatsapp_health_status() -> dict[str, object]:
    config = _meta_whatsapp_config()
    cloud_api_configured = bool(config["access_token"] and config["phone_number_id"])
    return {
        "status": "ok",
        "cloud_api_configured": cloud_api_configured,
        "template_configured": bool(config["template_name"]),
        "delivery_mode": "meta_cloud_api" if cloud_api_configured else "wa_link_only",
        "api_version": config["api_version"],
        "message": "Meta Cloud API configured." if cloud_api_configured else "Using wa.me link fallback mode.",
    }


def _send_meta_whatsapp_text(phone: str, message: str, config: dict[str, str]) -> bool:
    url = f"https://graph.facebook.com/{config['api_version']}/{config['phone_number_id']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message.strip(),
        },
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config['access_token']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.ok:
        logger.info("WhatsApp text message sent successfully to=%s", phone)
        return True

    logger.warning(
        "WhatsApp text send failed to=%s status=%s",
        phone,
        response.status_code,
    )
    return False


def _send_meta_whatsapp_template(phone: str, message: str, config: dict[str, str]) -> bool:
    url = f"https://graph.facebook.com/{config['api_version']}/{config['phone_number_id']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": config["template_name"],
            "language": {"code": config["template_language_code"]},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": message.strip()[:1024],
                        }
                    ],
                }
            ],
        },
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config['access_token']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.ok:
        logger.info("WhatsApp template message sent successfully to=%s template=%s", phone, config["template_name"])
        return True

    logger.warning(
        "WhatsApp template send failed to=%s status=%s template=%s",
        phone,
        response.status_code,
        config["template_name"],
    )
    return False


def send_whatsapp_message(phone: str, message: str) -> bool:
    """Send via Meta WhatsApp Cloud API when configured, otherwise log and fall back safely."""
    normalized_phone = _normalized_phone(phone)
    if not normalized_phone:
        logger.info("WhatsApp placeholder skipped because patient phone is unavailable.")
        return False

    config = _meta_whatsapp_config()
    # POLISH-8-WHATSAPP-UPDATES: External WhatsApp delivery is optional and falls back to wa.me links.
    if not is_whatsapp_enabled():
        logger.info("WhatsApp API disabled by ENABLE_WHATSAPP_API; using wa.me link flow for to=%s", normalized_phone)
        return False
    if config["access_token"] and config["phone_number_id"]:
        try:
            if config["template_name"]:
                sent = _send_meta_whatsapp_template(normalized_phone, message, config)
                if sent:
                    return True
            return _send_meta_whatsapp_text(normalized_phone, message, config)
        except requests.RequestException as exc:
            logger.warning("WhatsApp send failed because the Meta API request errored: %s", exc)
            return False

    logger.info("WhatsApp Cloud API is not configured; using wa.me link flow for to=%s", normalized_phone)
    return False


def build_whatsapp_link(phone: str, message: str) -> str:
    normalized_phone = _normalized_phone(phone)
    if not normalized_phone:
        return ""
    return f"https://wa.me/{normalized_phone}?text={quote((message or '').strip())}"
