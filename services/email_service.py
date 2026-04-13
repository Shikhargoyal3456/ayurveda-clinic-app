from __future__ import annotations

import logging
import smtplib
from email.utils import parseaddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


logger = logging.getLogger(__name__)


def send_email(recipient: str, subject: str, body: str, is_html: bool = False) -> bool:
    recipient = (recipient or "").strip()
    if not recipient:
        logger.info("Email skipped because recipient is missing.")
        return False
    _, parsed_email = parseaddr(recipient)
    if "@" not in parsed_email:
        logger.info("Email skipped because recipient is invalid: %s", recipient)
        return False
    if not (body or "").strip():
        logger.info("Email skipped because body is empty for recipient=%s.", recipient)
        return False
    if not settings.email_user or not settings.email_password:
        logger.info("Email skipped because SMTP credentials are not configured.")
        return False

    try:
        message = MIMEMultipart()
        message["From"] = settings.email_user
        message["To"] = parsed_email
        message["Subject"] = subject
        message.attach(MIMEText(body or "", "html" if is_html else "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(settings.email_user, settings.email_password)
            server.sendmail(settings.email_user, [parsed_email], message.as_string())
        logger.info("Email sent successfully to=%s", parsed_email)
        logger.info("Sent message to %s: email=%s", parsed_email, True)
        return True
    except Exception as exc:
        logger.exception("Email send failed to=%s: %s", recipient, exc)
        logger.info("Sent message to %s: email=%s", recipient, False)
        return False
