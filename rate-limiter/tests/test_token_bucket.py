import pytest

from ratelimiter import FakeClock, TokenBucketLimiter


def make_limiter(capacity=3, refill_rate=1.0, **kwargs):
    clock = FakeClock(start=1000.0)
    limiter = TokenBucketLimiter(
        capacity=capacity, refill_rate=refill_rate, clock=clock, **kwargs
    )
    return limiter, clock


def test_first_request_is_allowed():
    limiter, _ = make_limiter()
    assert limiter.allow("alice") is True


def test_bucket_starts_full_and_allows_a_burst_up_to_capacity():
    limiter, _ = make_limiter(capacity=3, refill_rate=1.0)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False  # bucket now empty


def test_tokens_refill_over_time():
    limiter, clock = make_limiter(capacity=2, refill_rate=1.0)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False  # empty

    clock.advance(1)  # +1 token at 1 token/sec
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False


def test_refill_is_capped_at_bucket_capacity():
    limiter, clock = make_limiter(capacity=2, refill_rate=1.0)
    limiter.allow("alice")  # 1 token left
    clock.advance(1000)  # would "refill" far past capacity
    # only 2 tokens should be available, not 1000+
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False


def test_partial_refill_not_enough_for_another_request():
    limiter, clock = make_limiter(capacity=1, refill_rate=1.0)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False

    clock.advance(0.5)  # only half a token available
    assert limiter.allow("alice") is False

    clock.advance(0.5)  # now a full token has accrued
    assert limiter.allow("alice") is True


def test_keys_are_isolated():
    limiter, _ = make_limiter(capacity=1, refill_rate=1.0)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice") is False

    assert limiter.allow("bob") is True
    assert limiter.allow("bob") is False


def test_reset_refills_the_bucket():
    limiter, _ = make_limiter(capacity=1, refill_rate=1.0)
    limiter.allow("alice")
    assert limiter.allow("alice") is False

    limiter.reset("alice")
    assert limiter.allow("alice") is True


@pytest.mark.parametrize("bad_kwarg", [{"capacity": 0}, {"capacity": -1}])
def test_rejects_invalid_capacity(bad_kwarg):
    with pytest.raises(ValueError):
        TokenBucketLimiter(refill_rate=1.0, **bad_kwarg)


@pytest.mark.parametrize("bad_kwarg", [{"refill_rate": 0}, {"refill_rate": -1}])
def test_rejects_invalid_refill_rate(bad_kwarg):
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=5, **bad_kwarg)
