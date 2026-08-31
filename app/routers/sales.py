from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter(tags=["sales"])


def _require_sales_api_key(api_key_header: str | None) -> None:
    api_key = os.getenv("SALES_API_KEY", "")
    if not api_key or api_key_header != api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/api/sales/leads")
def create_sales_lead(
    payload: dict[str, Any],
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _require_sales_api_key(x_api_key)
    return JSONResponse({"success": True, "lead": payload})
