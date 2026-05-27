from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, verify_csrf
from app.database import get_db
from app.portal_auth import get_portal_user, require_portal_roles
from models.user import User
from services.handwriting_recognition import HandwritingRecognitionService
from shared.template_engine import templates
from shared.template_engine import render_template


router = APIRouter(tags=["prescription-ocr"])
ocr_service = HandwritingRecognitionService()
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    return get_portal_user(request, db)


@router.get("/prescription/decode-handwriting")
def handwritten_decoder_page(request: Request, user: User = Depends(require_portal_roles("patient"))):
    return render_template(templates, request,
        "patient/handwriting_decoder.html",
        {
            "request": request,
            "simple_nav": "health",
            "active_page": "profile",
            "csrf_token": ensure_csrf_token(request),
            "user_name": user.full_name,
            "user_role": "Prescription decoder",
            "avatar_label": "".join(part[:1] for part in user.full_name.split()[:2]).upper()[:2] or "RX",
        },
    )


@router.post("/api/prescription/decode-handwriting")
async def decode_handwritten_prescription(
    request: Request,
    prescription_image: UploadFile = File(...),
    _: None = Depends(verify_csrf),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    content = await prescription_image.read()
    if not content:
        return JSONResponse({"success": False, "error": "Please upload a prescription image or PDF."}, status_code=400)
    if len(content) > MAX_UPLOAD_BYTES:
        return JSONResponse({"success": False, "error": "Prescription file must be 5MB or smaller."}, status_code=400)

    mime_type = str(prescription_image.content_type or "image/jpeg").strip() or "image/jpeg"
    image_base64 = base64.b64encode(content).decode("utf-8")
    image_data = f"data:{mime_type};base64,{image_base64}"

    result = await ocr_service.decode_prescription(image_data, mime_type=mime_type)
    if result.get("medicines"):
        result["medicines"] = await ocr_service.enhance_with_medicine_info(result["medicines"])

    logger.info("Prescription handwriting decoded for user_id=%s medicine_count=%s", user.id, len(result.get("medicines", [])))
    return {
        "success": True,
        "data": result,
        "message": "Prescription decoded from handwriting",
    }


@router.post("/prescription/enhance-image")
async def enhance_prescription_image(
    request: Request,
    prescription_image: UploadFile = File(...),
    _: None = Depends(verify_csrf),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    content = await prescription_image.read()
    if not content:
        return JSONResponse({"success": False, "error": "Please upload a prescription image or PDF."}, status_code=400)
    if len(content) > MAX_UPLOAD_BYTES:
        return JSONResponse({"success": False, "error": "Prescription file must be 5MB or smaller."}, status_code=400)

    mime_type = str(prescription_image.content_type or "image/jpeg").strip() or "image/jpeg"
    image_base64 = base64.b64encode(content).decode("utf-8")
    image_data = f"data:{mime_type};base64,{image_base64}"
    enhancement = ocr_service.enhance_image(image_data, mime_type=mime_type)
    return {"success": True, "data": enhancement}


@router.post("/prescription/suggest-medicine")
async def suggest_prescription_medicine(
    request: Request,
    query: str = Form(...),
    dosage_hint: str = Form(""),
    frequency_hint: str = Form(""),
    _: None = Depends(verify_csrf),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    suggestions = ocr_service.suggest_medicines(query, dosage_hint=dosage_hint, frequency_hint=frequency_hint)
    return {"success": True, "data": suggestions}


@router.get("/prescription/medicine-db")
def search_prescription_medicine_db(
    request: Request,
    q: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    results = ocr_service.search_medicine_database(q, limit=limit)
    return {"success": True, "data": results}


@router.post("/api/prescription/decoder-feedback")
async def submit_decoder_feedback(
    request: Request,
    medicine_name: str = Form(""),
    note: str = Form(""),
    _: None = Depends(verify_csrf),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    payload = ocr_service.submit_feedback({"medicine_name": medicine_name, "note": note, "user_id": user.id})
    logger.info("Prescription decoder feedback submitted by user_id=%s", user.id)
    return payload
