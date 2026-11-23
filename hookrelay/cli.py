"""``python -m hookrelay``: simulate a few deliveries and print a summary."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Mapping

from hookrelay.config import Settings
from hookrelay.ratelimit.registry import TenantRegistry
from hookrelay.webhooks.dispatcher import DeliveryResult, Dispatcher, Event, Response

# Scripted responses per event sequence number; anything else returns 200.
SCRIPT: dict[int, list[Response]] = {
    2: [Response(503), Response(200)],
    4: [Response(500), Response(500), Response(500)],
    5: [Response(429, {"Retry-After": "1"}), Response(200)],
    6: [Response(400)],
}

EVENTS = [
    Event("evt-1", "tenant-red", {"seq": 1, "type": "order.created"}),
    Event("evt-2", "tenant-blue", {"seq": 2, "type": "order.created"}),
    Event("evt-3", "tenant-red", {"seq": 3, "type": "order.paid"}),
    Event("evt-4", "tenant-green", {"seq": 4, "type": "order.created"}),
    Event("evt-5", "tenant-red", {"seq": 5, "type": "order.shipped"}),
    Event("evt-6", "tenant-blue", {"seq": 6, "type": "order.paid"}),
    Event("evt-7", "tenant-red", {"seq": 7, "type": "order.refunded"}),
    Event("evt-8", "tenant-red", {"seq": 8, "type": "order.created"}),
]


class FakeClock:
    """Simulated time: sleeping advances it, so the demo runs instantly."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class FakeTransport:
    """Answers from SCRIPT without touching the network."""

    def __init__(self) -> None:
        self._seen: dict[int, int] = {}

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str]) -> Response:
        seq = json.loads(body)["seq"]
        n = self._seen.get(seq, 0)
        self._seen[seq] = n + 1
        script = SCRIPT.get(seq, [])
        return script[n] if n < len(script) else Response(200)


def _quota(registry: TenantRegistry, tenant: str) -> str:
    return f"{int(registry.remaining(tenant))}/{int(registry.capacity)}"


def _retry_in(result: DeliveryResult) -> str:
    return "-" if result.retry_after is None else f"{result.retry_after:.1f}s"


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_dict(
        {
            "bucket_capacity": 8,
            "bucket_refill_per_sec": 1.0,
            "tenant_capacity": 3,
            "tenant_refill_per_sec": 0.5,
            "retry_jitter_sec": 0.0,
        }
    )
    clock = FakeClock()
    registry = TenantRegistry.from_settings(settings, clock)
    dispatcher = Dispatcher(
        FakeTransport(), settings, registry=registry, sleep=clock.sleep, clock=clock
    )

    print(
        f"{'EVENT':<7} {'TENANT':<13} {'RESULT':<20} {'STATUS':>6} "
        f"{'ATTEMPTS':>8} {'QUOTA':>5} {'RETRY-IN':>8}"
    )
    results: list[DeliveryResult] = []
    for event in EVENTS:
        result = dispatcher.deliver(event)
        results.append(result)
        status = "-" if result.status is None else str(result.status)
        print(
            f"{result.event_id:<7} {result.tenant:<13} {result.reason:<20} {status:>6} "
            f"{result.attempts:>8} {_quota(registry, result.tenant):>5} {_retry_in(result):>8}"
        )

    by_tenant: dict[str, list[DeliveryResult]] = defaultdict(list)
    for result in results:
        by_tenant[result.tenant].append(result)

    print(f"\n{'TENANT':<13} {'SENT':>4} {'FAILED':>6} {'LIMITED':>7} {'QUOTA':>5}")
    for tenant, rows in sorted(by_tenant.items()):
        sent = sum(r.delivered for r in rows)
        limited = sum(r.reason.endswith("rate_limited") for r in rows)
        failed = len(rows) - sent - limited
        print(f"{tenant:<13} {sent:>4} {failed:>6} {limited:>7} {_quota(registry, tenant):>5}")

    delivered = sum(r.delivered for r in results)
    print(f"\n{delivered}/{len(results)} delivered")
    return 0
