from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import ensure_csrf_token, verify_csrf
from app.database import get_db
from app.portal_auth import get_portal_user, require_portal_roles
from models.user import User
from services.lab_analyzer import LabReportAnalyzer, clean_extracted_text
from shared.template_engine import templates


router = APIRouter(tags=["lab-analyzer"])
analyzer = LabReportAnalyzer()
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
logger = logging.getLogger(__name__)


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    return get_portal_user(request, db)


@router.get("/lab-analyzer")
def lab_analyzer_page(request: Request, user: User = Depends(require_portal_roles("patient"))):
    return templates.TemplateResponse(
        request,
        "patient/lab_analyzer.html",
        {
            "request": request,
            "simple_nav": "health",
            "active_page": "profile",
            "csrf_token": ensure_csrf_token(request),
            "user_name": user.full_name,
            "user_role": "Patient",
            "avatar_label": "".join(part[:1] for part in user.full_name.split()[:2]).upper()[:2] or "PT",
            "page_hint": "Upload lab reports and get simple AI explanations",
        },
    )


@router.post("/api/lab-analyzer/analyze")
async def analyze_lab_report(
    request: Request,
    report: UploadFile = File(...),
    _: None = Depends(verify_csrf),
    user: User | None = Depends(get_current_user_optional),
):
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login/patient"})

    suffix = os.path.splitext(report.filename or "")[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        return JSONResponse({"success": False, "error": "Please upload a PDF, JPG, JPEG, or PNG file."}, status_code=400)

    content = await report.read()
    if not content:
        return JSONResponse({"success": False, "error": "The uploaded file is empty."}, status_code=400)

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        extracted_text = await analyzer.extract_text_from_report(tmp_path, report.content_type or suffix)
        readable_text = extracted_text.strip()
        logger.info(
            "Lab analyzer extraction result length=%s preview=%r",
            len(readable_text),
            readable_text[:500],
        )

        parsed = await analyzer.parse_lab_values(readable_text)
        analysis = await analyzer.analyze_with_ai(readable_text, parsed)

        analysis["summary"] = clean_extracted_text(str(analysis.get("summary") or ""))
        analysis["recommendations"] = [
            clean_extracted_text(str(item)) for item in (analysis.get("recommendations") or []) if str(item).strip()
        ]
        diagnosis = []
        for item in analysis.get("diagnosis", []) or []:
            diagnosis.append(
                {
                    "condition": clean_extracted_text(str(item.get("condition") or "")),
                    "confidence": clean_extracted_text(str(item.get("confidence") or "Low")).title() or "Low",
                    "evidence": [
                        clean_extracted_text(str(entry)) for entry in (item.get("evidence") or []) if str(entry).strip()
                    ],
                    "confirmatory_tests": [
                        clean_extracted_text(str(entry))
                        for entry in (item.get("confirmatory_tests") or [])
                        if str(entry).strip()
                    ],
                }
            )
        analysis["diagnosis"] = diagnosis
        for item in analysis.get("abnormal_findings", []) or []:
            item["meaning"] = clean_extracted_text(str(item.get("meaning") or ""))
            item["recommendation"] = clean_extracted_text(str(item.get("recommendation") or ""))
        for item in analysis.get("normal_findings", []) or []:
            item["test_name"] = clean_extracted_text(str(item.get("test_name") or ""))

        return JSONResponse({"success": True, **analysis})
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc), "source": "ai_error"}, status_code=503)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
