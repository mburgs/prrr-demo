"""Deliver events to a webhook endpoint with retries."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from hookrelay.config import Settings
from hookrelay.ratelimit.bucket import TokenBucket
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


# (url, body, headers) -> Response
Transport = Callable[[str, bytes, Mapping[str, str]], Response]


class Dispatcher:
    def __init__(
        self,
        transport: Transport,
        settings: Settings,
        *,
        sleep: Callable[[float], None] = time.sleep,
        bucket: TokenBucket | None = None,
    ) -> None:
        self._transport = transport
        self._settings = settings
        self._sleep = sleep
        self._bucket = bucket or TokenBucket(
            settings.bucket_capacity, settings.bucket_refill_per_sec
        )

    def deliver(self, event: Event) -> DeliveryResult:
        s = self._settings
        if not self._bucket.allow():
            return DeliveryResult(event.id, event.tenant, False, 0, None, "rate_limited")

        body = json.dumps(event.payload, sort_keys=True).encode()
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(s.secret, body),
        }

        status: int | None = None
        reason = "unknown"
        for attempt in range(1, s.retry_count + 1):
            try:
                response = self._transport(s.webhook_url, body, headers)
            except TransportError:
                status, reason = None, "transport_error"
            else:
                status = response.status
                if 200 <= status < 300:
                    return DeliveryResult(event.id, event.tenant, True, attempt, status, "ok")
                reason = f"http_{status}"
            if attempt < s.retry_count:
                self._sleep(s.retry_delay_sec)
        return DeliveryResult(event.id, event.tenant, False, s.retry_count, status, reason)
