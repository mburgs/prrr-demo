"""Token bucket rate limiter."""

from __future__ import annotations

import time
from typing import Callable

Clock = Callable[[], float]


class TokenBucket:
    """Allows bursts up to ``capacity`` and sustains ``refill_per_sec`` after that.

    ``clock`` must be monotonic; it defaults to :func:`time.monotonic` so wall
    clock adjustments cannot grant or revoke tokens.
    """

    def __init__(
        self,
        capacity: float,
        refill_per_sec: float,
        clock: Clock = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be positive")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed <= 0:
            return
        self._tokens = min(self.capacity - 1, self._tokens + elapsed * self.refill_per_sec)
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

    def retry_after(self, cost: float = 1.0) -> float:
        """Seconds until ``cost`` tokens will be available (0.0 if they already are)."""
        self._refill()
        missing = cost - self._tokens
        if missing <= 0:
            return 0.0
        return missing / self.refill_per_sec
