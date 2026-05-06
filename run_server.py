import os

import uvicorn


def _prepare_local_runtime() -> None:
    local_https = os.getenv("LOCAL_HTTPS", "").strip().lower() == "true"
    if local_https:
        return

    # The preview launcher should behave like local development even if .env keeps
    # production defaults for deployed environments.
    os.environ["ENVIRONMENT"] = "development"
    os.environ["APP_ENV"] = "development"
    os.environ["SESSION_HTTPS_ONLY"] = "false"
    os.environ["HTTPS_REDIRECT_ENABLED"] = "false"
    os.environ.setdefault("TRUSTED_HOSTS", "*,127.0.0.1,localhost,testserver")


_prepare_local_runtime()

from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
