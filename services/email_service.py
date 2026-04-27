from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi.concurrency import run_in_threadpool


logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "587").strip())
        self.sender_email = os.getenv("SENDER_EMAIL", "").strip()
        self.sender_password = os.getenv("SENDER_PASSWORD", "").strip()

    def is_configured(self) -> bool:
        return bool(self.sender_email and self.sender_password)

    def _send(self, subject: str, html_body: str, recipient: str) -> dict[str, object]:
        if not recipient:
            return {"success": False, "skipped": True, "reason": "missing_recipient"}
        if not self.is_configured():
            logger.info("Email skipped because SMTP is not configured.")
            return {"success": False, "skipped": True, "reason": "smtp_not_configured"}

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = recipient
        message.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, [recipient], message.as_string())
            return {"success": True}
        except Exception as exc:  # pragma: no cover
            logger.exception("Email send failed for %s: %s", recipient, exc)
            return {"success": False, "error": str(exc)}

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
        return await run_in_threadpool(self._send, subject, html, customer_email)

    async def send_order_status_update(self, order_id: int, status: str, customer_email: str) -> dict[str, object]:
        subject = f"Order #{order_id} status update"
        html = f"""
        <h2>Order Status Update</h2>
        <p>Your order <strong>#{order_id}</strong> is now <strong>{status}</strong>.</p>
        <p>Thank you for trusting Kash AI for your healthcare needs.</p>
        """
        return await run_in_threadpool(self._send, subject, html, customer_email)


def send_email(recipient: str, subject: str, message: str) -> bool:
    service = EmailService()
    result = service._send(subject, f"<p>{message}</p>", recipient)
    return bool(result.get("success"))
