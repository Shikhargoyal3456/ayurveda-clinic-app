import os
import argparse

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    port = int(os.getenv("PORT", args.port))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.reload,
    )
