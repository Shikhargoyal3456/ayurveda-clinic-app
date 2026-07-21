from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.database import commit_with_retry


def chunked_rows(rows: Sequence[Any], chunk_size: int = 1000):
    for start in range(0, len(rows), chunk_size):
        yield rows[start : start + chunk_size]


def bulk_insert(session: Session, rows: Iterable[Any], *, chunk_size: int = 1000) -> int:
    buffered = list(rows)
    if not buffered:
        return 0
    inserted = 0
    for chunk in chunked_rows(buffered, chunk_size=chunk_size):
        session.add_all(chunk)
        commit_with_retry(session)
        inserted += len(chunk)
    return inserted

