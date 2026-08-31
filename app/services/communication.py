from __future__ import annotations

import asyncio
import logging
from email.utils import parseaddr

from services.email_service import send_email
from services.sms_service import SMSService


logger = logging.getLogger(__name__)
sms_service = SMSService()


def send_patient_message(
    phone: str,
    email: str | None,
    message: str,
    subject: str = "Kash AI Update",
) -> dict[str, bool | str]:
    result = {"sms": False, "email": False, "whatsapp": False, "whatsapp_link": ""}
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
            sms_result = asyncio.run(sms_service.send_sms(phone, message))
            result["sms"] = bool(sms_result.get("success"))
            result["whatsapp"] = result["sms"]
        except Exception as exc:
            logger.exception("Patient SMS message failed: %s", exc)
        if not result["sms"]:
            try:
                logger.info("Retrying patient SMS message to=%s after first failure.", phone)
                sms_result = asyncio.run(sms_service.send_sms(phone, message))
                result["sms"] = bool(sms_result.get("success"))
                result["whatsapp"] = result["sms"]
            except Exception as exc:
                logger.exception("Patient SMS retry failed: %s", exc)
        logger.info("Sent message to %s: sms=%s", phone, result["sms"])

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
