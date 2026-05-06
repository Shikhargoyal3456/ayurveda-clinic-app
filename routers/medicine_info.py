from __future__ import annotations

import base64
import json
import mimetypes
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, commit_with_retry, get_db
from app.portal_auth import UPLOAD_ROOT, get_portal_user, require_portal_roles, user_public_context
from models.ai_features import AIPrescriptionScan
from models.medicine import MedicineOrder
from services.ai_prescription_analyzer import AIPrescriptionAnalyzer


router = APIRouter(tags=["medicine-info"])
templates = Jinja2Templates(directory=str(settings.templates_dir))
analyzer = AIPrescriptionAnalyzer()


def _save_bytes(raw_bytes: bytes, suffix: str, folder: str) -> str:
    target_dir = UPLOAD_ROOT / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / f"{secrets.token_hex(16)}{suffix}"
    destination.write_bytes(raw_bytes[:8_000_000])
    return str(destination)


def _prescription_record_or_404(db: Session, prescription_id: int) -> AIPrescriptionScan:
    record = db.get(AIPrescriptionScan, prescription_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return record


def _can_access_record(user, record: AIPrescriptionScan) -> bool:
    role = getattr(user.role, "value", str(user.role))
    if role in {"admin", "pharmacy_owner"}:
        return True
    if role == "doctor" and (record.doctor_user_id == user.id or record.user_id == user.id):
        return True
    return record.user_id == user.id


def _serialize_record(record: AIPrescriptionScan) -> dict[str, Any]:
    medicines = record.medicines if isinstance(record.medicines, list) else []
    total = round(sum(float(item.get("price", 0) or 0) * int(item.get("suggested_quantity", 1) or 1) for item in medicines), 2)
    return {
        "id": record.id,
        "title": record.title or f"Prescription #{record.id}",
        "image_url": f"/api/prescription/{record.id}/image" if record.image_url else "",
        "medicines": medicines,
        "confidence": float(record.confidence or 0),
        "status": record.status,
        "source_type": record.source_type,
        "file_type": record.file_type,
        "review_notes": record.review_notes or "",
        "estimated_total": total,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "order_url": f"/order-medicines?source=prescription&prescription_id={record.id}",
    }


@router.get("/api/prescription/{prescription_id}/image")
def prescription_image(
    prescription_id: int,
    user=Depends(require_portal_roles("patient", "doctor", "pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    record = _prescription_record_or_404(db, prescription_id)
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="Access denied")
    path = Path(record.image_url or "")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Prescription file not found")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(content=path.read_bytes(), media_type=media_type)


@router.get("/medicine/{medicine_name}")
def medicine_detail_page(request: Request, medicine_name: str):
    return templates.TemplateResponse(
        request,
        "patient/medicine_detail.html",
        {
            "request": request,
            "medicine_name": medicine_name,
            "active_page": "medicines",
            "user_name": "Medicine details",
            "user_role": "Patient education",
            "avatar_label": "MD",
        },
    )


@router.post("/api/prescription/analyze")
def analyze_prescription(
    request: Request,
    payload: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    image_data = str(payload.get("image", "")).strip()
    if not image_data:
        raise HTTPException(status_code=400, detail="No image provided")
    user = get_portal_user(request, db)
    result = analyzer.analyze_image_payload(db, image_data)
    raw = image_data.split(",", 1)[1] if image_data.startswith("data:") and "," in image_data else image_data
    file_bytes = base64.b64decode(raw.encode("utf-8"), validate=False)
    image_url = _save_bytes(file_bytes, ".jpg", "prescriptions")
    record = analyzer.persist_analysis(
        db,
        user_id=int(user.id if user else 0),
        title="Uploaded Prescription",
        image_url=image_url,
        file_type="image",
        result=result,
        source_type="patient_upload",
        status="pending",
    )
    response = dict(result)
    response.update({"id": record.id, "order_url": f"/order-medicines?source=prescription&prescription_id={record.id}"})
    return JSONResponse(response)


@router.post("/api/prescription/analyze-upload")
async def analyze_prescription_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_portal_user(request, db)
    file_bytes = await file.read()
    filename = file.filename or "prescription"
    result = analyzer.analyze_upload_bytes(db, file_bytes, filename)
    suffix = Path(filename).suffix.lower() or ".bin"
    image_url = _save_bytes(file_bytes, suffix, "prescriptions")
    record = analyzer.persist_analysis(
        db,
        user_id=int(user.id if user else 0),
        title=filename,
        image_url=image_url,
        file_type="pdf" if suffix == ".pdf" else "image",
        result=result,
        source_type="patient_upload",
        status="pending",
    )
    response = dict(result)
    response.update({"id": record.id, "order_url": f"/order-medicines?source=prescription&prescription_id={record.id}"})
    return JSONResponse(response)


@router.get("/api/prescription/history")
def prescription_history(request: Request, db: Session = Depends(get_db)):
    user = get_portal_user(request, db)
    if user is None:
        return JSONResponse([])
    return JSONResponse(analyzer.history_for_user(db, user.id))


@router.get("/api/prescription/{prescription_id}")
def prescription_detail(prescription_id: int, user=Depends(require_portal_roles("patient", "doctor", "pharmacy_owner", "admin")), db: Session = Depends(get_db)):
    record = _prescription_record_or_404(db, prescription_id)
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="Access denied")
    return JSONResponse(_serialize_record(record))


@router.get("/api/medicine/info/{medicine_name}")
def get_medicine_info(medicine_name: str, db: Session = Depends(get_db)):
    return JSONResponse(analyzer.get_medicine_info(db, medicine_name))


@router.post("/api/prescription/verify")
def verify_prescription(
    payload: dict[str, Any] = Body(...),
    user=Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    prescription_id = int(payload.get("prescription_id", 0) or 0)
    if prescription_id <= 0:
        raise HTTPException(status_code=400, detail="prescription_id is required")
    record = _prescription_record_or_404(db, prescription_id)
    result = analyzer.verify_record(db, record)
    return JSONResponse(result)


@router.post("/api/prescription/{prescription_id}/review")
def review_prescription(
    prescription_id: int,
    payload: dict[str, Any] = Body(default={}),
    user=Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    record = _prescription_record_or_404(db, prescription_id)
    status = str(payload.get("status", "verified")).strip().lower()
    if status not in {"verified", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="Unsupported status")
    analyzer.review_record(db, record, status=status, reviewer_user_id=user.id, note=str(payload.get("note", "")))
    return JSONResponse({"success": True, "prescription_id": record.id, "status": record.status})


@router.post("/api/prescription/check-interactions")
def check_interactions(
    payload: dict[str, Any] = Body(...),
    user=Depends(require_portal_roles("doctor", "admin")),
):
    medicines = payload.get("medicines", []) if isinstance(payload.get("medicines"), list) else []
    return JSONResponse(analyzer.check_interactions(medicines))


@router.post("/api/doctor/e-prescription/generate")
def generate_e_prescription(
    payload: dict[str, Any] = Body(...),
    user=Depends(require_portal_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    medicines = payload.get("medicines", []) if isinstance(payload.get("medicines"), list) else []
    if not medicines:
        raise HTTPException(status_code=400, detail="At least one medicine is required")
    enriched = analyzer.enhance_with_medicine_info(db, medicines)
    extracted_text = "\n".join(f"{item.get('name', 'Medicine')} {item.get('dosage', '')} {item.get('duration', '')}".strip() for item in enriched)
    result = {
        "extracted_text": extracted_text,
        "medicines": enriched,
        "confidence": 96,
        "estimated_total": round(sum(float(item.get("price", 0) or 0) for item in enriched), 2),
        "potential_savings": round(sum(float(item.get("savings", 0) or 0) for item in enriched), 2),
        "requires_review": False,
    }
    patient_name = str(payload.get("patient_name", "Patient")).strip() or "Patient"
    title = f"E-Prescription for {patient_name}"
    record = analyzer.persist_analysis(
        db,
        user_id=user.id,
        title=title,
        image_url="",
        file_type="generated",
        result=result,
        source_type="doctor_eprescription",
        doctor_user_id=user.id,
        status="verified",
    )
    record.review_notes = str(payload.get("notes", "")).strip() or "Generated from doctor portal."
    commit_with_retry(db)
    db.refresh(record)
    return JSONResponse(
        {
            "success": True,
            "prescription_id": record.id,
            "download_url": f"/api/prescription/{record.id}/download",
            "order_url": f"/order-medicines?source=prescription&prescription_id={record.id}",
            "share_message": f"E-prescription ready for {patient_name}.",
            "interaction_check": analyzer.check_interactions(medicines),
        }
    )


@router.get("/api/prescription/{prescription_id}/download")
def download_prescription_pdf(
    prescription_id: int,
    user=Depends(require_portal_roles("patient", "doctor", "pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    record = _prescription_record_or_404(db, prescription_id)
    if not _can_access_record(user, record):
        raise HTTPException(status_code=403, detail="Access denied")
    pdf_bytes = analyzer.build_pdf_bytes(record, doctor_name=getattr(user, "full_name", ""), patient_name=record.title.replace("E-Prescription for ", ""))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="prescription-{record.id}.pdf"'},
    )


@router.get("/api/pharmacy/orders/{order_id}/prescription")
def prescription_for_order(
    order_id: int,
    user=Depends(require_portal_roles("pharmacy_owner", "admin")),
    db: Session = Depends(get_db),
):
    order = db.get(MedicineOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        items = json.loads(order.medicines_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Order prescription metadata is invalid") from exc
    prescription_id = 0
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and str(item.get("source", "")).strip().lower() == "prescription":
            prescription_id = int(item.get("prescription_id", 0) or 0)
            if prescription_id:
                break
    if prescription_id <= 0:
        raise HTTPException(status_code=404, detail="No prescription attached")
    record = _prescription_record_or_404(db, prescription_id)
    payload = _serialize_record(record)
    payload.update(analyzer.verify_record(db, record))
    return JSONResponse(payload)
