"""Common interface all rate limiter policies implement."""

from abc import ABC, abstractmethod


class RateLimiter(ABC):
    """
    A rate limiter decides, per client key, whether a request should be
    allowed right now. Implementations are free to choose any internal
    policy (sliding window, token bucket, etc.) as long as they honour
    this interface, which is what callers depend on.
    """

    @abstractmethod
    def allow(self, key: str) -> bool:
        """
        Return True if a request for `key` is allowed right now (and
        record it as consumed), or False if the caller should be
        throttled.
        """
        raise NotImplementedError

    def reset(self, key: str) -> None:
        """
        Clear any state held for `key`. Optional — default is a no-op.
        Mainly useful for tests and admin tooling.
        """
        return None
