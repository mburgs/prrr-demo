"""Per-tenant token buckets with a bounded, least-recently-used working set."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from hookrelay.config import Settings
from hookrelay.ratelimit.bucket import Clock, TokenBucket


class TenantRegistry:
    """Lazily creates one :class:`TokenBucket` per tenant.

    At most ``max_tenants`` buckets are kept. When a new tenant would exceed
    the cap, the least recently *used* tenant is evicted; if it comes back
    later it starts over with a full bucket.
    """

    def __init__(
        self,
        capacity: float,
        refill_per_sec: float,
        max_tenants: int,
        clock: Clock = time.monotonic,
    ) -> None:
        if max_tenants < 1:
            raise ValueError("max_tenants must be at least 1")
        self._capacity = capacity
        self._refill_per_sec = refill_per_sec
        self._max_tenants = max_tenants
        self._clock = clock
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings, clock: Clock = time.monotonic) -> "TenantRegistry":
        return cls(
            settings.tenant_capacity,
            settings.tenant_refill_per_sec,
            settings.max_tenants,
            clock,
        )

    @property
    def capacity(self) -> float:
        return self._capacity

    def __len__(self) -> int:
        return len(self._buckets)

    def __contains__(self, tenant: object) -> bool:
        return tenant in self._buckets

    def allow(self, tenant: str, cost: float = 1.0) -> bool:
        """Take ``cost`` tokens from ``tenant``'s bucket, creating it on first use."""
        with self._lock:
            bucket = self._buckets.get(tenant)
            if bucket is None:
                bucket = TokenBucket(self._capacity, self._refill_per_sec, self._clock)
                self._buckets[tenant] = bucket
                if len(self._buckets) > self._max_tenants:
                    self._buckets.popitem(last=False)
            else:
                self._buckets.move_to_end(tenant)
            return bucket.allow(cost)

    def remaining(self, tenant: str) -> float:
        """Tokens currently available to ``tenant``. Does not create or refresh a bucket."""
        with self._lock:
            bucket = self._buckets.get(tenant)
            return self._capacity if bucket is None else bucket.remaining

    def retry_after(self, tenant: str, cost: float = 1.0) -> float:
        """Seconds until ``tenant`` can spend ``cost`` tokens. Does not create a bucket."""
        with self._lock:
            bucket = self._buckets.get(tenant)
            return 0.0 if bucket is None else bucket.retry_after(cost)

    def snapshot(self) -> dict[str, float]:
        """Remaining tokens for every tracked tenant, least recently used first."""
        with self._lock:
            return {tenant: bucket.remaining for tenant, bucket in self._buckets.items()}
