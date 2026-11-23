"""``python -m hookrelay``: simulate a few deliveries and print a summary."""

from __future__ import annotations

import json
from typing import Mapping

from hookrelay.config import Settings
from hookrelay.webhooks.dispatcher import Dispatcher, Event, Response

# Scripted responses per event sequence number; anything else returns 200.
SCRIPT: dict[int, list[int]] = {
    2: [503, 200],
    4: [500, 500, 500],
    6: [400, 400, 400],
}

EVENTS = [
    Event("evt-1", "tenant-red", {"seq": 1, "type": "order.created"}),
    Event("evt-2", "tenant-blue", {"seq": 2, "type": "order.created"}),
    Event("evt-3", "tenant-red", {"seq": 3, "type": "order.paid"}),
    Event("evt-4", "tenant-green", {"seq": 4, "type": "order.created"}),
    Event("evt-5", "tenant-red", {"seq": 5, "type": "order.shipped"}),
    Event("evt-6", "tenant-blue", {"seq": 6, "type": "order.paid"}),
    Event("evt-7", "tenant-red", {"seq": 7, "type": "order.refunded"}),
]


class FakeTransport:
    """Answers from SCRIPT without touching the network."""

    def __init__(self) -> None:
        self._seen: dict[int, int] = {}

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str]) -> Response:
        seq = json.loads(body)["seq"]
        n = self._seen.get(seq, 0)
        self._seen[seq] = n + 1
        script = SCRIPT.get(seq, [])
        return Response(script[n] if n < len(script) else 200)


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_dict({"bucket_capacity": 8, "bucket_refill_per_sec": 1.0})
    dispatcher = Dispatcher(FakeTransport(), settings, sleep=lambda _s: None)

    print(f"{'EVENT':<8} {'TENANT':<13} {'RESULT':<20} {'STATUS':>6} {'ATTEMPTS':>8}")
    delivered = 0
    results = []
    for event in EVENTS:
        result = dispatcher.deliver(event)
        results.append(result)
        delivered += result.delivered
        status = "-" if result.status is None else str(result.status)
        print(
            f"{result.event_id:<8} {result.tenant:<13} {result.reason:<20} "
            f"{status:>6} {result.attempts:>8}"
        )
    print(f"\n{delivered}/{len(results)} delivered")
    return 0
