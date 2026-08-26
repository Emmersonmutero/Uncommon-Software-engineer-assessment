"""Injectable clock so rate limiter behaviour is deterministic in tests."""

from abc import ABC, abstractmethod
import time


class Clock(ABC):
    """Anything that can report "now" as a float number of seconds."""

    @abstractmethod
    def now(self) -> float:
        """Return the current time in seconds."""
        raise NotImplementedError


class SystemClock(Clock):
    """Wraps the real wall clock. Used in production."""

    def now(self) -> float:
        return time.time()


class FakeClock(Clock):
    """A controllable clock for tests. Never touches real time."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot move a clock backwards")
        self._now += seconds

    def set(self, value: float) -> None:
        self._now = value
