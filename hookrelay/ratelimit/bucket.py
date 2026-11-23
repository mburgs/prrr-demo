"""Token bucket rate limiter."""

from __future__ import annotations

import time


class TokenBucket:
    """Allows bursts up to ``capacity`` and sustains ``refill_per_sec`` after that."""

    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be positive")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._tokens = float(capacity)
        self._last = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
        self._last = now

    @property
    def remaining(self) -> float:
        self._refill()
        return self._tokens

    def allow(self, cost: float = 1.0) -> bool:
        """Take ``cost`` tokens if available. Returns False when the bucket is dry."""
        self._refill()
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False
