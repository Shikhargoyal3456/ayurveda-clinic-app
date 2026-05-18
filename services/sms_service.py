from __future__ import annotations

import logging
import os
from typing import Any

import requests


logger = logging.getLogger(__name__)


def _support_phone() -> str:
    return os.getenv("SUPPORT_PHONE", "9350397175").strip() or "9350397175"


def _normalize_phone(phone: str) -> str:
    digits = "".join(character for character in str(phone or "").strip() if character.isdigit())
    if len(digits) == 10:
        return digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


class SMSService:
    """Send SMS using Fast2SMS or MSG91 without Twilio."""

    def __init__(self):
        self.fast2sms_api_key = os.getenv("FAST2SMS_API_KEY", "").strip()
        self.fast2sms_sender_id = os.getenv("FAST2SMS_SENDER_ID", "KASHAI").strip() or "KASHAI"
        self.msg91_auth_key = os.getenv("MSG91_AUTH_KEY", "").strip()
        self.msg91_sender_id = os.getenv("MSG91_SENDER_ID", "KASHAI").strip() or "KASHAI"
        self.msg91_route = os.getenv("MSG91_ROUTE", "4").strip() or "4"
        self.preferred_provider = os.getenv("SMS_PROVIDER", "").strip().lower()

    def is_configured(self) -> bool:
        return bool(self.fast2sms_api_key or self.msg91_auth_key)

    def _send_via_fast2sms(self, phone: str, message: str) -> dict[str, Any]:
        response = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            json={
                "route": "dlt",
                "sender_id": self.fast2sms_sender_id,
                "message": message,
                "numbers": phone,
            },
            headers={
                "authorization": self.fast2sms_api_key,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text[:500]}
        if response.ok and payload.get("return"):
            return {"success": True, "provider": "fast2sms", "message_id": payload.get("request_id")}
        return {"success": False, "provider": "fast2sms", "error": payload.get("message") or f"HTTP {response.status_code}"}

    def _send_via_msg91(self, phone: str, message: str) -> dict[str, Any]:
        response = requests.post(
            "https://api.msg91.com/api/v5/flow/",
            json={
                "sender": self.msg91_sender_id,
                "route": self.msg91_route,
                "mobiles": f"91{phone}",
                "message": message,
            },
            headers={
                "authkey": self.msg91_auth_key,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text[:500]}
        if response.ok and str(payload.get("type", "")).lower() != "error":
            return {"success": True, "provider": "msg91", "message_id": payload.get("request_id") or payload.get("message")}
        return {"success": False, "provider": "msg91", "error": payload.get("message") or f"HTTP {response.status_code}"}

    async def send_sms(self, phone: str, message: str) -> dict[str, Any]:
        clean_phone = _normalize_phone(phone)
        clean_message = str(message or "").strip()
        if not clean_phone:
            return {"success": False, "skipped": True, "reason": "missing_phone"}
        if not clean_message:
            return {"success": False, "skipped": True, "reason": "missing_message"}
        if not self.is_configured():
            logger.info("SMS skipped because no SMS provider is configured.")
            return {"success": False, "skipped": True, "reason": "sms_not_configured"}

        providers = []
        if self.preferred_provider == "msg91" and self.msg91_auth_key:
            providers = [self._send_via_msg91]
            if self.fast2sms_api_key:
                providers.append(self._send_via_fast2sms)
        elif self.preferred_provider == "fast2sms" and self.fast2sms_api_key:
            providers = [self._send_via_fast2sms]
            if self.msg91_auth_key:
                providers.append(self._send_via_msg91)
        else:
            if self.fast2sms_api_key:
                providers.append(self._send_via_fast2sms)
            if self.msg91_auth_key:
                providers.append(self._send_via_msg91)

        last_error = "sms_provider_unavailable"
        for provider in providers:
            try:
                result = provider(clean_phone, clean_message)
                if result.get("success"):
                    return result
                last_error = str(result.get("error") or last_error)
            except requests.RequestException as exc:
                last_error = str(exc)
                logger.warning("SMS provider request failed: %s", exc)
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
                logger.exception("SMS provider failed unexpectedly: %s", exc)
        return {"success": False, "error": last_error}

    async def send_prescription_alert(self, phone: str, patient_name: str, doctor_name: str) -> dict[str, Any]:
        message = (
            f"KASH AI: Dear {patient_name}, Dr. {doctor_name} has sent your prescription. "
            f"Please check your email. Help: {_support_phone()}"
        )
        return await self.send_sms(phone, message)

    async def send_followup_reminder(self, phone: str, patient_name: str, followup_date: str) -> dict[str, Any]:
        message = (
            f"KASH AI: Reminder for {patient_name}'s follow-up on {followup_date}. "
            f"For help call {_support_phone()}."
        )
        return await self.send_sms(phone, message)

    async def send_order_update(self, phone: str, order_id: int, status: str) -> dict[str, Any]:
        status_map = {
            "confirmed": f"KASH AI: Order #{order_id} confirmed. We will update you again soon.",
            "shipped": f"KASH AI: Order #{order_id} shipped and is on the way.",
            "dispatched": f"KASH AI: Order #{order_id} dispatched and is on the way.",
            "delivered": f"KASH AI: Order #{order_id} delivered. Thank you for choosing Kash AI.",
        }
        message = status_map.get(status, f"KASH AI: Order #{order_id} status updated to {status}.")
        return await self.send_sms(phone, message)
