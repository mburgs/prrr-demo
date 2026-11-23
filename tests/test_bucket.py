import pytest

from hookrelay.ratelimit.bucket import TokenBucket


def drain(bucket: TokenBucket) -> int:
    count = 0
    while bucket.allow():
        count += 1
    return count


def test_fresh_bucket_allows_full_burst(clock):
    assert drain(TokenBucket(5, 1.0, clock)) == 5


def test_denies_when_empty(clock):
    bucket = TokenBucket(2, 1.0, clock)
    assert bucket.allow() and bucket.allow()
    assert not bucket.allow()


def test_refills_over_time(clock):
    bucket = TokenBucket(4, 1.0, clock)
    drain(bucket)
    clock.advance(2)
    assert drain(bucket) == 2


def test_fractional_refill_accumulates(clock):
    bucket = TokenBucket(3, 1.0, clock)
    drain(bucket)
    clock.advance(0.5)
    assert not bucket.allow()
    clock.advance(0.5)
    assert bucket.allow()


def test_never_exceeds_capacity(clock):
    bucket = TokenBucket(3, 10.0, clock)
    drain(bucket)
    clock.advance(1000)
    assert drain(bucket) <= 3


def test_clock_going_backwards_is_ignored(clock):
    bucket = TokenBucket(2, 1.0, clock)
    drain(bucket)
    clock.advance(-50)
    assert not bucket.allow()


def test_rejects_bad_parameters():
    with pytest.raises(ValueError):
        TokenBucket(0, 1.0)
    with pytest.raises(ValueError):
        TokenBucket(1, 0)


def test_retry_after_is_zero_when_tokens_available(clock):
    assert TokenBucket(3, 1.0, clock).retry_after() == 0.0


def test_retry_after_reports_time_to_next_token(clock):
    bucket = TokenBucket(2, 4.0, clock)
    drain(bucket)
    assert bucket.retry_after() == pytest.approx(0.25)
    clock.advance(0.1)
    assert bucket.retry_after() == pytest.approx(0.15)


def test_retry_after_scales_with_cost(clock):
    bucket = TokenBucket(10, 2.0, clock)
    drain(bucket)
    assert bucket.retry_after(cost=4) == pytest.approx(2.0)


def test_waiting_retry_after_makes_allow_succeed(clock):
    bucket = TokenBucket(3, 2.0, clock)
    drain(bucket)
    clock.advance(bucket.retry_after())
    assert bucket.allow()
