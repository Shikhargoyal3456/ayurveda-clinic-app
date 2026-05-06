from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import settings
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

templates = Jinja2Templates(directory=TEMPLATE_DIRECTORIES)
templates.env.globals["NAVIGATION"] = NAVIGATION
templates.env.globals["APP_NAME"] = settings.clinic_name
