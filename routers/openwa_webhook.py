"""OpenWA webhook handler for incoming WhatsApp messages."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.database import SessionLocal
from services.openwa_service import get_openwa_service
from routers.whatsapp_patient import process_patient_whatsapp_message


router = APIRouter(prefix="/api/openwa", tags=["OpenWA Webhook"])


async def process_incoming_message(chat_id: str, message: str) -> str:
    db = SessionLocal()
    try:
        result = await process_patient_whatsapp_message(
            db=db,
            chat_id=chat_id,
            message_body=message,
            request=None,
        )
        return str(result.get("reply") or "").strip()
    finally:
        db.close()


@router.post("/webhook")
async def openwa_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-OpenWA-Signature", "")
    secret = settings.openwa_webhook_secret
    if secret and signature:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if signature != f"sha256={expected}":
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    data = await request.json()
    event = str(data.get("event") or "").strip()
    if event == "message.received":
        payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        chat_id = str(payload.get("chatId") or payload.get("from") or "").strip()
        message_body = str(payload.get("body") or "").strip()
        from_me = bool(payload.get("fromMe"))
        if chat_id and message_body and not from_me:
            response_text = await process_incoming_message(chat_id, message_body)
            if response_text:
                await get_openwa_service().send_text(chat_id, response_text)
    return {"status": "ok"}


@router.get("/session")
async def openwa_session_status():
    service = get_openwa_service()
    return await service.get_session_status()


@router.get("/qr")
async def openwa_qr():
    service = get_openwa_service()
    return await service.get_qr()


@router.post("/start")
async def openwa_start():
    service = get_openwa_service()
    return await service.start_session()


@router.post("/pairing-code")
async def openwa_pairing_code(request: Request):
    payload = await request.json()
    phone_number = str(payload.get("phone_number") or payload.get("phoneNumber") or "").strip()
    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required")
    return await get_openwa_service().request_pairing_code(phone_number)
