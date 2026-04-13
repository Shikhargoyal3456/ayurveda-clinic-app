from __future__ import annotations

import inspect
import os
from functools import wraps
from typing import Any, Callable

from app.analytics import log_error


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def safe_execute(func: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                log_error("safe_execute_failure", str(exc), {"function": getattr(func, "__name__", "unknown")})
                return None

        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            log_error("safe_execute_failure", str(exc), {"function": getattr(func, "__name__", "unknown")})
            return None

    return wrapper
