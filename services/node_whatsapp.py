from __future__ import annotations

import logging
import os
from typing import Any

import requests


logger = logging.getLogger(__name__)


def _service_url() -> str:
    return (os.getenv("NODE_WHATSAPP_SERVICE_URL") or "http://127.0.0.1:3000").rstrip("/")


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _medicine_payload(medicines: list[dict[str, Any]]) -> dict[str, str]:
    if not medicines:
        return {
            "medicine": "Prescription medicines",
            "dosage": "As prescribed",
            "frequency": "As prescribed",
        }

    if len(medicines) == 1:
        medicine = medicines[0]
        return {
            "medicine": _first_non_empty(medicine.get("name"), "Prescription medicines"),
            "dosage": _first_non_empty(medicine.get("dosage"), "As prescribed"),
            "frequency": _first_non_empty(medicine.get("frequency"), "As prescribed"),
        }

    names = []
    dosage_parts = []
    frequency_parts = []
    for medicine in medicines:
        name = _first_non_empty(medicine.get("name"))
        if not name:
            continue
        names.append(name)
        dosage = _first_non_empty(medicine.get("dosage"))
        frequency = _first_non_empty(medicine.get("frequency"))
        if dosage:
            dosage_parts.append(f"{name}: {dosage}")
        if frequency:
            frequency_parts.append(f"{name}: {frequency}")

    return {
        "medicine": "; ".join(names) or "Prescription medicines",
        "dosage": "; ".join(dosage_parts) or "As prescribed",
        "frequency": "; ".join(frequency_parts) or "As prescribed",
    }


def send_prescription_via_node_whatsapp(
    *,
    patient_name: str,
    patient_phone: str,
    diagnosis: str,
    medicines: list[dict[str, Any]],
    advice: str,
    duration: str,
    doctor_name: str,
) -> dict[str, Any]:
    """Send a prescription through the Node/Twilio WhatsApp service.

    The caller should treat any exception or unsuccessful response as a soft
    failure and fall back to the app's existing wa.me flow.
    """
    if not patient_phone:
        return {"sent": False, "error": "patient phone missing"}

    medicine_fields = _medicine_payload(medicines)
    payload = {
        "patientName": patient_name,
        "patientPhone": patient_phone,
        "condition": diagnosis,
        "medicine": medicine_fields["medicine"],
        "dosage": medicine_fields["dosage"],
        "frequency": medicine_fields["frequency"],
        "duration": duration or "As prescribed",
        "doctor": doctor_name,
        "advice": advice,
    }

    try:
        response = requests.post(
            f"{_service_url()}/prescriptions",
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.warning("Node WhatsApp prescription send failed: %s", exc)
        return {"sent": False, "error": str(exc)}

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:500]}

    if response.ok:
        notification = body.get("notification", {}) if isinstance(body, dict) else {}
        return {
            "sent": True,
            "status_code": response.status_code,
            "message_sid": notification.get("messageSid"),
            "status": notification.get("status"),
            "response": body,
        }

    logger.warning("Node WhatsApp prescription send rejected: status=%s body=%s", response.status_code, body)
    return {
        "sent": False,
        "status_code": response.status_code,
        "response": body,
    }
