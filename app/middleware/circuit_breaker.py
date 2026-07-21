from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from time import monotonic
from typing import Any, Awaitable, Callable

try:
    from circuitbreaker import circuit
except Exception:  # pragma: no cover
    circuit = None


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0.0


_STATES: dict[str, CircuitState] = defaultdict(CircuitState)
_LIMITS: dict[str, asyncio.Semaphore] = {}


def concurrency_limiter(name: str, limit: int = 4) -> asyncio.Semaphore:
    if name not in _LIMITS:
        _LIMITS[name] = asyncio.Semaphore(limit)
    return _LIMITS[name]


def circuit_breaker(name: str, failure_threshold: int = 3, recovery_seconds: int = 30):
    def decorator(func: Callable[..., Any]):
        if circuit is not None:
            return circuit(failure_threshold=failure_threshold, recovery_timeout=recovery_seconds)(func)

        async def async_wrapper(*args: Any, **kwargs: Any):
            state = _STATES[name]
            if state.opened_until and monotonic() < state.opened_until:
                raise RuntimeError(f"{name} circuit is open")
            try:
                return await func(*args, **kwargs)
            except Exception:
                state.failures += 1
                if state.failures >= failure_threshold:
                    state.opened_until = monotonic() + recovery_seconds
                    state.failures = 0
                raise

        return async_wrapper

    return decorator

