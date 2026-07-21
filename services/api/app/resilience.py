"""Bounded retry and circuit-breaker primitives for external providers."""

from __future__ import annotations

import random
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

from .operations import record_domain_event


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


class CircuitOpenError(urllib.error.URLError):
    """Provider is temporarily blocked after repeated failures."""


class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._states: dict[str, CircuitState] = {}
        self._lock = threading.Lock()

    def before_call(self, provider: str) -> None:
        with self._lock:
            state = self._states.setdefault(provider, CircuitState())
            if state.opened_at is None:
                return
            if time.monotonic() - state.opened_at >= self.reset_seconds:
                state.opened_at = None
                state.failures = 0
                record_domain_event("provider_circuit", f"{provider}:half_open")
                return
            raise CircuitOpenError(f"provider circuit open: {provider}")

    def success(self, provider: str) -> None:
        with self._lock:
            self._states[provider] = CircuitState()

    def failure(self, provider: str) -> None:
        with self._lock:
            state = self._states.setdefault(provider, CircuitState())
            state.failures += 1
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()
                record_domain_event("provider_circuit", f"{provider}:open")


provider_circuits = ProviderCircuitBreaker()


def resilient_urlopen(
    provider: str,
    request: urllib.request.Request,
    *,
    timeout: float,
    attempts: int = 2,
):
    """Open a request with capped exponential backoff and circuit breaking."""
    attempts = max(1, min(attempts, 3))
    last_error: Exception | None = None
    for attempt in range(attempts):
        provider_circuits.before_call(provider)
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
            provider_circuits.success(provider)
            if attempt:
                record_domain_event("provider_retry_recovered", provider)
            return response
        except Exception as exc:
            last_error = exc
            provider_circuits.failure(provider)
            record_domain_event("provider_failure", provider)
            if attempt + 1 < attempts:
                time.sleep((0.05 * (2**attempt)) + random.uniform(0.0, 0.025))
    assert last_error is not None
    raise last_error
