from __future__ import annotations

import logging
from email.utils import parseaddr

from services.email_service import send_email
from services.whatsapp import build_whatsapp_link, send_whatsapp_message


logger = logging.getLogger(__name__)


def send_patient_message(
    phone: str,
    email: str | None,
    message: str,
    subject: str = "Kash AI Update",
) -> dict[str, bool | str]:
    result = {"whatsapp": False, "email": False, "whatsapp_link": ""}
    phone = (phone or "").strip()
    email = (email or "").strip() if email else ""
    message = (message or "").strip()

    if not message:
        logger.info("Patient message skipped because message is empty.")
        return result
    if not phone and not email:
        logger.info("Patient message skipped because no contact method is available.")
        return result

    if phone:
        try:
            result["whatsapp"] = send_whatsapp_message(phone, message)
        except Exception as exc:
            logger.exception("Patient WhatsApp message failed: %s", exc)
        if not result["whatsapp"]:
            try:
                logger.info("Retrying patient WhatsApp message to=%s after first failure.", phone)
                result["whatsapp"] = send_whatsapp_message(phone, message)
            except Exception as exc:
                logger.exception("Patient WhatsApp retry failed: %s", exc)
        if not result["whatsapp"]:
            result["whatsapp_link"] = build_whatsapp_link(phone, message)
        logger.info("Sent message to %s: whatsapp=%s", phone, result["whatsapp"])

    try:
        if email:
            _, parsed_email = parseaddr(email)
            if "@" in parsed_email:
                result["email"] = send_email(parsed_email, subject, message)
            else:
                logger.info("Patient email skipped because address is invalid: %s", email)
    except Exception as exc:
        logger.exception("Patient email message failed: %s", exc)
    if email:
        logger.info("Sent message to %s: email=%s", email, result["email"])

    return result
