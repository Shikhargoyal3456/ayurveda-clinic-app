from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.template_compat import patch_jinja2_templates
from core.navigation import NAVIGATION


TEMPLATE_DIRECTORIES = [
    str(settings.shared_templates_dir),
    str(settings.base_dir / "apps" / "patient" / "templates"),
    str(settings.base_dir / "apps" / "pharmacy" / "templates"),
    str(settings.base_dir / "apps" / "doctor" / "templates"),
    str(settings.base_dir / "apps" / "lab" / "templates"),
    str(settings.base_dir / "apps" / "delivery" / "templates"),
    str(settings.templates_dir),
]

patch_jinja2_templates()
templates = Jinja2Templates(directory=TEMPLATE_DIRECTORIES)
templates.env.globals["NAVIGATION"] = NAVIGATION
templates.env.globals["APP_NAME"] = settings.clinic_name


def render_template(
    templates_obj: Jinja2Templates,
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    **kwargs: Any,
):
    """Render a template using the provided Jinja2Templates instance."""
    payload = dict(context or {})
    payload["request"] = request
    return templates_obj.TemplateResponse(request, template_name, payload, **kwargs)
