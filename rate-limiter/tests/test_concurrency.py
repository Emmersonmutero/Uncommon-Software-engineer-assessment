"""
Thread-safety tests.

These use the real SystemClock (not FakeClock) because we're exercising
genuine concurrent access from multiple OS threads. The assertion is on
*counts*, not timing, so it stays deterministic despite using real time.
"""

import threading

import pytest

from ratelimiter import SlidingWindowLimiter, TokenBucketLimiter


@pytest.mark.parametrize(
    "limiter_factory",
    [
        lambda: SlidingWindowLimiter(max_requests=100, window_seconds=60),
        lambda: TokenBucketLimiter(capacity=100, refill_rate=0.001),
    ],
    ids=["sliding_window", "token_bucket"],
)
def test_exactly_capacity_requests_succeed_under_concurrent_load(limiter_factory):
    limiter = limiter_factory()
    key = "shared-key"
    num_threads = 50
    attempts_per_thread = 10  # 500 total attempts against a limit of 100

    allowed_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal allowed_count
        local_allowed = 0
        for _ in range(attempts_per_thread):
            if limiter.allow(key):
                local_allowed += 1
        with lock:
            allowed_count += local_allowed

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Under a race condition (e.g. missing locks) this would exceed the
    # limit. With correct locking it must be exactly capacity, since the
    # refill rate is negligible over the test's short runtime.
    assert allowed_count == 100


def test_concurrent_access_to_different_keys_does_not_interfere():
    limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
    num_keys = 20
    results = {}
    lock = threading.Lock()

    def worker(key):
        allowed = [limiter.allow(key) for _ in range(8)]
        with lock:
            results[key] = allowed

    threads = [
        threading.Thread(target=worker, args=(f"key-{i}",)) for i in range(num_keys)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for key, allowed in results.items():
        assert allowed == [True] * 5 + [False] * 3, f"unexpected result for {key}"
