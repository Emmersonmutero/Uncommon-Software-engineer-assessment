import pytest

from ratelimiter import FakeClock, SlidingWindowLimiter


def make_limiter(max_requests=3, window_seconds=10, **kwargs):
    clock = FakeClock(start=1000.0)
    limiter = SlidingWindowLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
        clock=clock,
        **kwargs,
    )
    return limiter, clock


def test_first_request_is_always_allowed():
    limiter, _ = make_limiter()
    assert limiter.allow("alice") is True


def test_allows_up_to_the_limit_then_blocks():
    limiter, _ = make_limiter(max_requests=3, window_seconds=10)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    # 4th request within the same window must be rejected
    assert limiter.allow("alice") is False


def test_window_boundary_exact_expiry():
    limiter, clock = make_limiter(max_requests=2, window_seconds=10)
    assert limiter.allow("alice") is True  # t=1000
    clock.advance(5)
    assert limiter.allow("alice") is True  # t=1005, still within window of first
    assert limiter.allow("alice") is False  # limit reached

    # Move exactly to the moment the first request expires (t=1010,
    # cutoff = now - window = 1000, and the first request was AT 1000,
    # so it should now be evicted: <= cutoff).
    clock.advance(5)  # t=1010
    assert limiter.allow("alice") is True

    # But one bucket slot is now used again (from t=1005's request,
    # which is still within the last 10s), so the next one should fail.
    assert limiter.allow("alice") is False


def test_window_slides_gradually_not_in_fixed_buckets():
    limiter, clock = make_limiter(max_requests=1, window_seconds=10)
    assert limiter.allow("alice") is True  # t=1000
    clock.advance(9)
    assert limiter.allow("alice") is False  # t=1009, still inside window

    clock.advance(2)  # t=1011, first request (t=1000) has expired
    assert limiter.allow("alice") is True


def test_burst_traffic_within_limit_all_succeed():
    limiter, _ = make_limiter(max_requests=5, window_seconds=10)
    results = [limiter.allow("alice") for _ in range(5)]
    assert results == [True] * 5


def test_burst_traffic_exceeding_limit_only_first_n_succeed():
    limiter, _ = make_limiter(max_requests=5, window_seconds=10)
    results = [limiter.allow("alice") for _ in range(8)]
    assert results == [True] * 5 + [False] * 3


def test_keys_are_isolated_from_each_other():
    limiter, _ = make_limiter(max_requests=2, window_seconds=10)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False

    # Bob has never made a request, so he is unaffected by Alice's usage.
    assert limiter.allow("bob") is True
    assert limiter.allow("bob") is True
    assert limiter.allow("bob") is False


def test_reset_clears_state_for_a_key():
    limiter, _ = make_limiter(max_requests=1, window_seconds=10)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False

    limiter.reset("alice")
    assert limiter.allow("alice") is True


def test_idle_keys_are_evicted_after_ttl():
    limiter, clock = make_limiter(
        max_requests=1, window_seconds=10, idle_ttl_seconds=20
    )
    limiter.allow("alice")
    assert "alice" in limiter._requests  # white-box check

    # Advance well past window (so the log empties) and past idle_ttl,
    # then trigger another call for a different key to run cleanup.
    clock.advance(50)
    limiter.allow("bob")

    assert "alice" not in limiter._requests
    assert "alice" not in limiter._last_seen


@pytest.mark.parametrize("bad_kwarg", [{"max_requests": 0}, {"max_requests": -1}])
def test_rejects_invalid_max_requests(bad_kwarg):
    with pytest.raises(ValueError):
        SlidingWindowLimiter(window_seconds=10, **bad_kwarg)


@pytest.mark.parametrize("bad_kwarg", [{"window_seconds": 0}, {"window_seconds": -5}])
def test_rejects_invalid_window(bad_kwarg):
    with pytest.raises(ValueError):
        SlidingWindowLimiter(max_requests=5, **bad_kwarg)
