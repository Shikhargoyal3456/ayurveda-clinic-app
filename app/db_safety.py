from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable, TypeVar

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)
T = TypeVar("T")


@contextmanager
def safe_db_operation(db: Session):
    try:
        yield db
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.error("Database integrity error: %s", exc)
        raise ValueError("Data integrity violation") from exc
    except OperationalError as exc:
        db.rollback()
        logger.error("Database operational error: %s", exc)
        raise ConnectionError("Database connection issue") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database query error: %s", exc)
        raise RuntimeError("Database operation failed") from exc
    except Exception:
        db.rollback()
        logger.exception("Unexpected database operation error")
        raise


def with_db_retry(fetcher: Callable[[], T], attempts: int = 3, base_delay_seconds: float = 0.25) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetcher()
        except OperationalError as exc:
            last_error = exc
            logger.warning("Database operation failed on attempt %s/%s: %s", attempt, attempts, exc)
            if attempt == attempts:
                break
            time.sleep(base_delay_seconds * attempt)
    if last_error is not None:
        raise ConnectionError("Database operation failed after retries") from last_error
    raise RuntimeError("Database retry wrapper failed unexpectedly")


def safe_fetch_all(fetcher: Callable[[], Iterable[T]]) -> list[T]:
    try:
        return list(fetcher() or [])
    except Exception as exc:
        logger.error("Fetch all failed: %s", exc)
        return []


def safe_fetch_one(fetcher: Callable[[], T | None]) -> T | None:
    try:
        return with_db_retry(fetcher)
    except Exception as exc:
        logger.error("Fetch one failed: %s", exc)
        return None


def safe_execute(executor: Callable[[], Any]) -> bool:
    try:
        executor()
        return True
    except Exception as exc:
        logger.error("Execute failed: %s", exc)
        return False
