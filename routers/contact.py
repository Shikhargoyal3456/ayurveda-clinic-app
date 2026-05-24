from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from app.config import settings
from app.security import Sanitizer


logger = logging.getLogger(__name__)
router = APIRouter(tags=["contact"])
templates = Jinja2Templates(directory=str(settings.templates_dir))

SUPPORT_PHONE = "9350397175"
SUPPORT_EMAIL = "goyalshikhar67@gmail.com"
SUPPORT_WHATSAPP = "919350397175"
SMTP_SERVER = os.getenv("CONTACT_SMTP_SERVER", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("CONTACT_SMTP_PORT", "587") or "587")
SMTP_USERNAME = os.getenv("CONTACT_EMAIL_USER", SUPPORT_EMAIL).strip()
SMTP_PASSWORD = os.getenv("CONTACT_EMAIL_PASSWORD", "").strip()


class ContactForm(BaseModel):
    name: str
    email: str
    phone: str | None = None
    subject: str
    message: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return Sanitizer.sanitize_email(value)


@router.get("/contact")
def contact_page(request: Request):
    return templates.TemplateResponse(
        request,
        "contact.html",
        {
            "request": request,
            "support_phone": SUPPORT_PHONE,
            "support_email": SUPPORT_EMAIL,
            "support_whatsapp": SUPPORT_WHATSAPP,
            "simple_nav": "contact",
            "page_hint": "Call, WhatsApp, email, or send a message",
        },
    )


@router.post("/api/contact/submit")
async def submit_contact_form(form: ContactForm):
    body = (
        f"New message from {form.name}\n\n"
        f"Email: {form.email}\n"
        f"Phone: {form.phone or 'Not provided'}\n"
        f"Subject: {form.subject}\n\n"
        f"Message:\n{form.message}\n"
    )

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("Contact form email not configured. Message received for %s.", SUPPORT_EMAIL)
        return {"success": True, "message": "Message received. We will get back to you soon."}

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = SUPPORT_EMAIL
        msg["Subject"] = f"Contact Form: {form.subject}"
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return {"success": True, "message": "Message sent successfully"}
    except Exception as exc:  # pragma: no cover
        logger.exception("Contact form email send failed: %s", exc)
        return JSONResponse(
            {"success": True, "message": "Message received. We will get back to you soon."},
            status_code=200,
        )
