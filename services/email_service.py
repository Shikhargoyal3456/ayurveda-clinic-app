from __future__ import annotations

import logging
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool


logger = logging.getLogger(__name__)


def _is_placeholder_recipient(recipient: str) -> bool:
    normalized = str(recipient or "").strip().lower()
    return normalized.endswith("@example.com")


def _support_phone() -> str:
    return os.getenv("SUPPORT_PHONE", "9350397175").strip() or "9350397175"


def _support_email() -> str:
    return os.getenv("SUPPORT_EMAIL", "support@kashai.local").strip() or "support@kashai.local"


class EmailService:
    """Send app notifications over Gmail-compatible SMTP."""

    def __init__(self):
        self.smtp_server = os.getenv("SMTP_HOST", os.getenv("SMTP_SERVER", "smtp.gmail.com")).strip() or "smtp.gmail.com"
        self.smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
        self.sender_email = os.getenv(
            "SMTP_USER",
            os.getenv("SENDER_EMAIL", os.getenv("EMAIL_USER", "")),
        ).strip()
        self.sender_password = os.getenv(
            "SMTP_PASSWORD",
            os.getenv("SENDER_PASSWORD", os.getenv("EMAIL_PASSWORD", "")),
        ).strip()

    def is_configured(self) -> bool:
        return bool(self.sender_email and self.sender_password)

    def missing_config_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.sender_email:
            missing.append("EMAIL_USER")
        if not self.sender_password:
            missing.append("EMAIL_PASSWORD")
        return missing

    def configuration_error_message(self) -> str:
        missing = self.missing_config_fields()
        if not missing:
            return ""
        return f"Email is not configured. Missing required setting(s): {', '.join(missing)}."

    def _send(
        self,
        subject: str,
        html_body: str,
        recipient: str,
        *,
        text_body: str = "",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        if not recipient:
            return {"success": False, "skipped": True, "reason": "missing_recipient"}
        if _is_placeholder_recipient(recipient):
            logger.warning("Skipping email send to placeholder recipient: %s", recipient)
            return {"success": False, "skipped": True, "reason": "placeholder_recipient"}
        if not self.is_configured():
            error_message = self.configuration_error_message()
            logger.warning("%s", error_message)
            return {
                "success": False,
                "skipped": True,
                "reason": "smtp_not_configured",
                "error": error_message,
                "missing_fields": self.missing_config_fields(),
            }

        message = MIMEMultipart("mixed")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = recipient

        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(text_body or "Please view this message in HTML format.", "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        message.attach(body_part)

        for attachment in attachments or []:
            filename = str(attachment.get("filename", "attachment.bin")).strip() or "attachment.bin"
            content = attachment.get("content", b"")
            if not isinstance(content, (bytes, bytearray)):
                continue
            part = MIMEBase("application", "octet-stream")
            part.set_payload(bytes(content))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            message.attach(part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, [recipient], message.as_string())
            return {"success": True}
        except Exception as exc:  # pragma: no cover
            logger.exception("Email send failed for %s: %s", recipient, exc)
            return {"success": False, "error": str(exc)}

    async def send_html_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str = "",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        return await run_in_threadpool(
            self._send,
            subject,
            html_body,
            to_email,
            text_body=text_body,
            attachments=attachments,
        )

    async def send_order_confirmation(self, order_details: dict[str, object], customer_email: str) -> dict[str, object]:
        subject = f"Order #{order_details.get('id')} confirmed"
        items_html = "".join(
            f"<li>{item.get('qty', 1)} x {item.get('name', 'Medicine')} - Rs {item.get('line_total', item.get('price', 0))}</li>"
            for item in order_details.get("items", [])
            if isinstance(item, dict)
        )
        html = f"""
        <h2>Order Confirmed</h2>
        <p>Your order <strong>#{order_details.get('id')}</strong> has been placed successfully.</p>
        <ul>{items_html}</ul>
        <p><strong>Total:</strong> Rs {order_details.get('total_amount', order_details.get('total', 0))}</p>
        <p>You can track your order from your Kash AI account.</p>
        """
        return await self.send_html_email(
            to_email=customer_email,
            subject=subject,
            html_body=html,
            text_body=f"Your order #{order_details.get('id')} has been confirmed.",
        )

    async def send_order_status_update(self, order_id: int, status: str, customer_email: str) -> dict[str, object]:
        subject = f"Order #{order_id} status update"
        html = f"""
        <h2>Order Status Update</h2>
        <p>Your order <strong>#{order_id}</strong> is now <strong>{status}</strong>.</p>
        <p>Thank you for trusting Kash AI for your healthcare needs.</p>
        """
        return await self.send_html_email(
            to_email=customer_email,
            subject=subject,
            html_body=html,
            text_body=f"Your order #{order_id} is now {status}.",
        )

    async def send_prescription(
        self,
        *,
        to_email: str,
        patient_name: str,
        doctor_name: str,
        diagnosis: str,
        medicines: list[dict[str, Any]],
        doctor_notes: str = "",
        followup_date: str = "",
        pdf_bytes: bytes | None = None,
        pdf_filename: str = "prescription.pdf",
    ) -> dict[str, object]:
        subject = f"Your Prescription from Dr. {doctor_name}"
        medicine_rows = "".join(
            (
                "<tr>"
                f"<td>{str(item.get('name', 'Medicine')).strip() or 'Medicine'}</td>"
                f"<td>{str(item.get('dosage', 'As directed')).strip() or 'As directed'}</td>"
                f"<td>{str(item.get('duration', 'As prescribed')).strip() or 'As prescribed'}</td>"
                f"<td>{str(item.get('frequency', item.get('instructions', 'Take as directed'))).strip() or 'Take as directed'}</td>"
                "</tr>"
            )
            for item in medicines
            if isinstance(item, dict)
        )
        if not medicine_rows:
            medicine_rows = "<tr><td colspan='4'>No medicines listed.</td></tr>"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; background: #f7f9fb; margin: 0; padding: 24px;">
            <div style="max-width: 640px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; border: 1px solid #dbe5ea;">
                <div style="background: #0F4C5C; color: white; padding: 24px; text-align: center;">
                    <h2 style="margin: 0;">KASH AI - Your Prescription</h2>
                </div>
                <div style="padding: 24px;">
                    <p>Dear {patient_name},</p>
                    <p>Dr. {doctor_name} has shared your prescription.</p>
                    <p><strong>Diagnosis:</strong> {diagnosis or 'Not specified'}</p>
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <tr>
                            <th style="border: 1px solid #d9e1e8; padding: 8px; text-align: left; background: #eef4f7;">Medicine</th>
                            <th style="border: 1px solid #d9e1e8; padding: 8px; text-align: left; background: #eef4f7;">Dosage</th>
                            <th style="border: 1px solid #d9e1e8; padding: 8px; text-align: left; background: #eef4f7;">Duration</th>
                            <th style="border: 1px solid #d9e1e8; padding: 8px; text-align: left; background: #eef4f7;">Instructions</th>
                        </tr>
                        {medicine_rows}
                    </table>
                    <p><strong>Next Follow-up:</strong> {followup_date or 'As advised by your doctor'}</p>
                    <p><strong>Doctor's Note:</strong> {doctor_notes or 'No additional notes recorded.'}</p>
                    <p style="margin-top: 28px; font-size: 12px; color: #667784;">
                        This is a system generated prescription from KASH AI.<br>
                        For any queries, contact: {_support_phone()} | {_support_email()}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = (
            f"Dear {patient_name},\n\n"
            f"Dr. {doctor_name} has shared your prescription.\n"
            f"Diagnosis: {diagnosis or 'Not specified'}\n"
            f"Follow-up: {followup_date or 'As advised by your doctor'}\n"
            f"Support: {_support_phone()} | {_support_email()}"
        )
        attachments = []
        if pdf_bytes:
            attachments.append({"filename": pdf_filename, "content": pdf_bytes})
        return await self.send_html_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
        )

    async def send_followup_reminder(
        self,
        *,
        to_email: str,
        patient_name: str,
        followup_date: str,
        doctor_name: str,
        confirmation_link: str = "",
    ) -> dict[str, object]:
        subject = "Follow-up Reminder - KASH AI"
        confirmation_html = (
            f'<p><a href="{confirmation_link}" style="background: #2BAE66; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Confirm Appointment</a></p>'
            if confirmation_link
            else ""
        )
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body>
            <div style="font-family: Arial; max-width: 500px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0F4C5C;">Follow-up Reminder</h2>
                <p>Dear {patient_name},</p>
                <p>This is a reminder for your follow-up consultation with <strong>Dr. {doctor_name}</strong>.</p>
                <p><strong>Scheduled Date:</strong> {followup_date}</p>
                {confirmation_html}
                <hr>
                <p style="font-size: 12px; color: #666;">KASH AI - Integrated Healthcare Platform</p>
            </div>
        </body>
        </html>
        """
        text_body = (
            f"Dear {patient_name}, this is a reminder for your follow-up consultation with Dr. {doctor_name} "
            f"on {followup_date}."
        )
        return await self.send_html_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )


def send_email(recipient: str, subject: str, message: str) -> bool:
    service = EmailService()
    result = service._send(subject, f"<p>{message}</p>", recipient, text_body=message)
    return bool(result.get("success"))
