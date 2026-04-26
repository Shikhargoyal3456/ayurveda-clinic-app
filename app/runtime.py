from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.config import settings


@dataclass
class RuntimeSnapshot:
    enabled: bool
    limit: int
    in_flight: int
    available_slots: int
    queue_timeout_seconds: float


class RequestLoadController:
    def __init__(self, max_concurrent_requests: int, queue_timeout_seconds: float) -> None:
        self.enabled = max_concurrent_requests > 0
        self.limit = max(0, max_concurrent_requests)
        self.queue_timeout_seconds = max(0.05, queue_timeout_seconds)
        self._semaphore = asyncio.Semaphore(self.limit) if self.enabled else None
        self._in_flight = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        if not self.enabled or self._semaphore is None:
            return True
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.queue_timeout_seconds)
        except TimeoutError:
            return False

        async with self._lock:
            self._in_flight += 1
        return True

    async def release(self) -> None:
        if not self.enabled or self._semaphore is None:
            return
        async with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
        self._semaphore.release()

    def snapshot(self) -> RuntimeSnapshot:
        available_slots = 0
        if self.enabled and self._semaphore is not None:
            available_slots = max(0, self.limit - self._in_flight)
        return RuntimeSnapshot(
            enabled=self.enabled,
            limit=self.limit,
            in_flight=self._in_flight,
            available_slots=available_slots,
            queue_timeout_seconds=self.queue_timeout_seconds,
        )


request_load_controller = RequestLoadController(
    max_concurrent_requests=settings.max_concurrent_requests,
    queue_timeout_seconds=settings.overload_queue_timeout_seconds,
)
