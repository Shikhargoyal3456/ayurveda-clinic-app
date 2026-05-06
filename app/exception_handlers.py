from __future__ import annotations

import logging
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    return uuid.uuid4().hex[:8]


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    requested_with = request.headers.get("x-requested-with", "").lower()
    return "/api/" in request.url.path or "application/json" in accept or requested_with == "xmlhttprequest"


def _friendly_message(detail: object, status_code: int) -> str:
    text = str(detail or "").strip()
    lowered = text.lower()

    if status_code == status.HTTP_429_TOO_MANY_REQUESTS or "too many" in lowered:
        return "Too many attempts. Please wait 1 minute."
    if "token expired" in lowered or "session expired" in lowered:
        return "Session expired. Please login again."
    if "phone number must be 10 digits" in lowered:
        return "Enter a valid 10-digit phone number."
    if "select at least one medicine" in lowered:
        return "Please add at least one medicine."
    if "medicine not found" in lowered:
        return "This medicine is out of stock."
    if "pharmacy not found" in lowered:
        return "No nearby medicine store is ready right now. Please try again."
    if "order not found" in lowered:
        return "We could not find that order."
    if "payment verification is temporarily unavailable" in lowered:
        return "Payment is taking a little longer. Please try again."
    if "invalid request data" in lowered:
        return "Please check the details and try again."
    if "server is busy" in lowered:
        return "Too many people are using the app right now. Please try again shortly."
    if not text:
        return "Something went wrong. Please try again."
    return text


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(location) for location in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Please check the details and try again.",
                "detail": "Please check the details and try again.",
                "details": details,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if 300 <= exc.status_code < 400 and exc.headers and exc.headers.get("Location"):
            return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)

        message = _friendly_message(exc.detail, exc.status_code)
        if _wants_json(request):
            payload = {"success": False, "error": message, "detail": message}
            if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                payload["retry_after"] = exc.headers.get("Retry-After") if exc.headers else None
            return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

        return HTMLResponse(
            status_code=exc.status_code,
            content=(
                "<!DOCTYPE html><html><head><title>Request issue</title></head>"
                "<body style=\"font-family: sans-serif; text-align:center; padding:50px;\">"
                f"<h1>{exc.status_code}</h1><p>{message}</p><p><a href=\"/\">Return to Homepage</a></p>"
                "</body></html>"
            ),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_id = generate_error_id()
        logger.error("Unhandled exception at path=%s error_id=%s", request.url.path, error_id)
        logger.error(traceback.format_exc())

        if _wants_json(request):
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": "Something went wrong. Please try again.",
                    "error_id": error_id,
                },
            )

        return HTMLResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=(
                "<!DOCTYPE html><html><head><title>Something went wrong</title></head>"
                "<body style=\"font-family: sans-serif; text-align:center; padding:50px;\">"
                "<h1>Something went wrong</h1>"
                "<p>We've been notified and are working on it.</p>"
                f"<p>Error ID: {error_id}</p>"
                "<p><a href=\"/\">Return to Homepage</a></p>"
                "</body></html>"
            ),
        )
