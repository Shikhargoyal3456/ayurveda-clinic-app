from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.template_compat import patch_jinja2_templates
from apps.patient.routes import patient_dashboard_context


def _request() -> Request:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static"), name="static")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "session": {},
        "app": app,
        "router": app.router,
    }
    return Request(scope)


def test_patient_dashboard_context_always_keeps_request():
    request = _request()
    context = patient_dashboard_context(request)
    assert context["request"] is request


def test_template_response_legacy_signature_injects_request():
    patch_jinja2_templates()
    templates = Jinja2Templates(directory=str(Path("templates")))
    request = _request()

    response = templates.TemplateResponse(request, "privacy.html", {})

    assert response.context["request"] is request
