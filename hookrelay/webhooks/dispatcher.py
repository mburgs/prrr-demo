"""Deliver events to a webhook endpoint with retries."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from hookrelay.config import Settings
from hookrelay.ratelimit.bucket import Clock, TokenBucket
from hookrelay.ratelimit.registry import TenantRegistry
from hookrelay.webhooks.signing import SIGNATURE_HEADER, sign


class TransportError(Exception):
    """Raised by a transport when the request could not be completed."""


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    id: str
    tenant: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class DeliveryResult:
    event_id: str
    tenant: str
    delivered: bool
    attempts: int
    status: int | None
    reason: str
    # Set when the event was refused locally: seconds until it could be accepted.
    retry_after: float | None = None


# (url, body, headers) -> Response
Transport = Callable[[str, bytes, Mapping[str, str]], Response]


def _is_retryable(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    """Parse a delta-seconds ``Retry-After`` header; HTTP-dates are ignored."""
    for name, value in headers.items():
        if name.lower() == "retry-after":
            try:
                seconds = float(value)
            except ValueError:
                return None
            return seconds if seconds >= 0 else None
    return None


class Dispatcher:
    def __init__(
        self,
        transport: Transport,
        settings: Settings,
        *,
        registry: TenantRegistry | None = None,
        bucket: TokenBucket | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
        clock: Clock = time.monotonic,
    ) -> None:
        self._transport = transport
        self._settings = settings
        self._sleep = sleep
        self._rand = rand
        self._registry = (
            registry if registry is not None else TenantRegistry.from_settings(settings, clock)
        )
        self._bucket = (
            bucket
            if bucket is not None
            else TokenBucket(settings.bucket_capacity, settings.bucket_refill_per_sec, clock)
        )

    def _backoff(self, attempt: int) -> float:
        """Delay after the ``attempt``-th failure (1-based): exponential, capped, jittered."""
        s = self._settings
        delay = min(s.retry_max_delay_sec, s.retry_delay_sec * 2 ** (attempt - 1))
        return delay + self._rand() * s.retry_jitter_sec

    def _delay(self, attempt: int, hinted: float | None) -> float:
        if hinted is not None:
            return min(hinted, self._settings.retry_max_delay_sec)
        return self._backoff(attempt)

    def deliver(self, event: Event) -> DeliveryResult:
        s = self._settings
        if not self._registry.allow(event.tenant):
            return DeliveryResult(
                event.id,
                event.tenant,
                False,
                0,
                None,
                "tenant_rate_limited",
                self._registry.retry_after(event.tenant),
            )
        if not self._bucket.allow():
            return DeliveryResult(
                event.id,
                event.tenant,
                False,
                0,
                None,
                "rate_limited",
                self._bucket.retry_after(),
            )

        body = json.dumps(event.payload, sort_keys=True).encode()
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(s.secret, body),
        }

        status: int | None = None
        reason = "unknown"
        attempts = 0
        while attempts < s.max_attempts:
            attempts += 1
            hinted: float | None = None
            try:
                response = self._transport(s.webhook_url, body, headers)
            except TransportError:
                status, reason = None, "transport_error"
            else:
                status = response.status
                if 200 <= status < 300:
                    return DeliveryResult(event.id, event.tenant, True, attempts, status, "ok")
                reason = f"http_{status}"
                if not _is_retryable(status):
                    break
                hinted = _retry_after_seconds(response.headers)
            if attempts < s.max_attempts:
                self._sleep(self._delay(attempts, hinted))
        return DeliveryResult(event.id, event.tenant, False, attempts, status, reason)
