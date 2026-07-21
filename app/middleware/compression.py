from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware


def build_compression_middleware(minimum_size: int = 512) -> GZipMiddleware:
    """
    FastAPI/Starlette compression wrapper.

    Starlette does not ship Brotli support out of the box, so we enable gzip
    at the middleware layer and let clients negotiate Accept-Encoding.
    """

    return GZipMiddleware(minimum_size=minimum_size)
