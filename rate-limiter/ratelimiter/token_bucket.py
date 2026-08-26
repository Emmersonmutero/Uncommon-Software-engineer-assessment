"""Token-bucket rate limiter — an interchangeable policy behind the same interface."""

import threading
from typing import Dict, Optional, Tuple

from .interfaces import RateLimiter
from .clock import Clock, SystemClock


class TokenBucketLimiter(RateLimiter):
    """
    Each key owns a bucket holding up to `capacity` tokens, refilling
    continuously at `refill_rate` tokens/second. Every allowed request
    consumes one token. This permits short bursts up to `capacity`
    while enforcing a long-run average rate of `refill_rate` req/s —
    a different trade-off from the sliding window's hard cap per
    fixed-length window.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        clock: Optional[Clock] = None,
        idle_ttl_seconds: Optional[float] = None,
    ):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")

        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._clock = clock or SystemClock()
        self._idle_ttl = (
            idle_ttl_seconds
            if idle_ttl_seconds is not None
            else (self._capacity / self._refill_rate) * 10
        )

        self._lock = threading.Lock()
        # key -> (tokens_remaining, last_refill_time)
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._last_cleanup_at: Optional[float] = None

    def allow(self, key: str) -> bool:
        now = self._clock.now()
        with self._lock:
            tokens, last_refill = self._buckets.get(key, (self._capacity, now))
            elapsed = max(0.0, now - last_refill)
            tokens = min(self._capacity, tokens + elapsed * self._refill_rate)

            if tokens >= 1.0:
                tokens -= 1.0
                allowed = True
            else:
                allowed = False

            self._buckets[key] = (tokens, now)
            self._maybe_cleanup(now)
            return allowed

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def _maybe_cleanup(self, now: float) -> None:
        if self._last_cleanup_at is None:
            self._last_cleanup_at = now
            return
        if now - self._last_cleanup_at < self._idle_ttl:
            return
        self._last_cleanup_at = now

        stale = [
            k
            for k, (tokens, last) in self._buckets.items()
            if now - last > self._idle_ttl and tokens >= self._capacity
        ]
        for k in stale:
            self._buckets.pop(k, None)
