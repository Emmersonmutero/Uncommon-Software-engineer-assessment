"""Exact sliding-window rate limiter (log-based, not fixed buckets)."""

import threading
from collections import deque
from typing import Deque, Dict, Optional

from .interfaces import RateLimiter
from .clock import Clock, SystemClock


class SlidingWindowLimiter(RateLimiter):
    """
    Allows at most `max_requests` requests per `window_seconds`, per key,
    using a precise sliding window: each key keeps a rolling log of the
    timestamps of its recent requests. On every call we drop timestamps
    older than `now - window_seconds` and then check if there's room.

    This avoids the classic "fixed window" bug where a client can send
    2x the limit by clustering requests around a window boundary.

    Storage is in-memory (dict of deques), guarded by a single lock.
    The public surface is just `allow(key)`, so the storage layer could
    be swapped for a distributed backend (e.g. Redis sorted sets, where
    ZREMRANGEBYSCORE + ZCARD + ZADD run atomically in a Lua script or
    MULTI/EXEC) without changing any caller code — see README for notes
    on what else changes under a distributed deployment.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Optional[Clock] = None,
        idle_ttl_seconds: Optional[float] = None,
    ):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self._max_requests = max_requests
        self._window = float(window_seconds)
        self._clock = clock or SystemClock()

        # How long a key may sit idle (no requests, empty log) before we
        # forget about it entirely, so memory doesn't grow unboundedly
        # for keys that show up once and never come back.
        self._idle_ttl = (
            idle_ttl_seconds if idle_ttl_seconds is not None else self._window * 10
        )

        self._lock = threading.Lock()
        self._requests: Dict[str, Deque[float]] = {}
        self._last_seen: Dict[str, float] = {}

        # Cleanup is opportunistic and throttled so it doesn't add O(n)
        # work to every single `allow()` call.
        self._cleanup_interval = self._idle_ttl
        self._last_cleanup_at: Optional[float] = None

    def allow(self, key: str) -> bool:
        now = self._clock.now()
        with self._lock:
            dq = self._requests.setdefault(key, deque())
            self._evict_expired(dq, now)

            if len(dq) < self._max_requests:
                dq.append(now)
                allowed = True
            else:
                allowed = False

            self._last_seen[key] = now
            self._maybe_cleanup(now)
            return allowed

    def reset(self, key: str) -> None:
        with self._lock:
            self._requests.pop(key, None)
            self._last_seen.pop(key, None)

    def _evict_expired(self, dq: Deque[float], now: float) -> None:
        cutoff = now - self._window
        while dq and dq[0] <= cutoff:
            dq.popleft()

    def _maybe_cleanup(self, now: float) -> None:
        if self._last_cleanup_at is None:
            self._last_cleanup_at = now
            return
        if now - self._last_cleanup_at < self._cleanup_interval:
            return
        self._last_cleanup_at = now

        # A key's deque is only trimmed when THAT key is accessed via
        # allow(), so a key that has simply gone quiet can still be
        # holding expired timestamps. During cleanup we trim every
        # candidate key's deque too, so idle keys are correctly
        # identified and evicted instead of lingering forever.
        stale_keys = []
        for k, last in list(self._last_seen.items()):
            if now - last <= self._idle_ttl:
                continue
            dq = self._requests.get(k)
            if dq:
                self._evict_expired(dq, now)
            if not dq:
                stale_keys.append(k)

        for k in stale_keys:
            self._requests.pop(k, None)
            self._last_seen.pop(k, None)
