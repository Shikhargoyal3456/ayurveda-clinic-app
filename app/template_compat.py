from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from fastapi.templating import Jinja2Templates


def patch_jinja2_templates() -> None:
    if getattr(Jinja2Templates, "_kash_ai_request_patch", False):
        return

    original_template_response = Jinja2Templates.TemplateResponse
    signature = inspect.signature(original_template_response)
    param_names = list(signature.parameters)
    request_first = len(param_names) > 1 and param_names[1] == "request"

    def _normalize_context(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError("Template context must be a mapping.")

    def _call_original(self, request: Any, template_name: str, context: dict[str, Any], *args: Any, **kwargs: Any):
        if request_first:
            return original_template_response(self, request, template_name, context, *args, **kwargs)
        return original_template_response(self, template_name, context, *args, **kwargs)

    def _patched_template_response(self, *args, **kwargs):
        request = kwargs.pop("request", None)

        if args and hasattr(args[0], "scope"):
            request = args[0]
            if len(args) < 2:
                raise TypeError("TemplateResponse() missing template name.")
            template_name = args[1]
            context = _normalize_context(args[2] if len(args) > 2 else kwargs.pop("context", None))
            if request is not None:
                context["request"] = request
            remaining_args = args[3:]
            return _call_original(self, request, template_name, context, *remaining_args, **kwargs)

        if not args:
            raise TypeError("TemplateResponse() missing template name.")

        template_name = args[0]
        context = _normalize_context(args[1] if len(args) > 1 else kwargs.pop("context", None))
        request = request or context.get("request")
        if request is None:
            raise ValueError('context must include a "request" key')
        context["request"] = request
        remaining_args = args[2:]
        return _call_original(self, request, template_name, context, *remaining_args, **kwargs)

    Jinja2Templates.TemplateResponse = _patched_template_response
    Jinja2Templates._kash_ai_request_patch = True
