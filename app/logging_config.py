from __future__ import annotations

import json
import logging
import contextvars
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        base = super().format(record)
        return f"{color}{base}{self.RESET}" if color else base


def _build_file_handler() -> RotatingFileHandler:
    handler = RotatingFileHandler(DEFAULT_LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    return handler


def _build_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ColoredFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    return handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_build_file_handler())
    logger.addHandler(_build_console_handler())
    logger.propagate = False
    return logger


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_ayurveda_logging_configured", False):
        return
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(_build_file_handler())
    root.addHandler(_build_console_handler())
    root._ayurveda_logging_configured = True  # type: ignore[attr-defined]


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def clear_request_id() -> None:
    _request_id.set("-")
