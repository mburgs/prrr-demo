import pytest

from hookrelay.ratelimit.bucket import TokenBucket


@pytest.fixture
def now(monkeypatch):
    """Controllable replacement for time.time()."""
    state = {"t": 1000.0}
    monkeypatch.setattr("time.time", lambda: state["t"])

    def advance(seconds: float) -> None:
        state["t"] += seconds

    return advance


def drain(bucket: TokenBucket) -> int:
    count = 0
    while bucket.allow():
        count += 1
    return count


def test_fresh_bucket_allows_full_burst(now):
    assert drain(TokenBucket(5, 1.0)) == 5


def test_denies_when_empty(now):
    bucket = TokenBucket(2, 1.0)
    assert bucket.allow() and bucket.allow()
    assert not bucket.allow()


def test_refills_over_time(now):
    bucket = TokenBucket(4, 1.0)
    drain(bucket)
    now(2)
    assert drain(bucket) == 2


def test_fractional_refill_accumulates(now):
    bucket = TokenBucket(3, 1.0)
    drain(bucket)
    now(0.5)
    assert not bucket.allow()
    now(0.5)
    assert bucket.allow()


def test_never_exceeds_capacity(now):
    bucket = TokenBucket(3, 10.0)
    drain(bucket)
    now(1000)
    assert drain(bucket) <= 3


def test_clock_going_backwards_is_ignored(now):
    bucket = TokenBucket(2, 1.0)
    drain(bucket)
    now(-50)
    assert not bucket.allow()


def test_rejects_bad_parameters():
    with pytest.raises(ValueError):
        TokenBucket(0, 1.0)
    with pytest.raises(ValueError):
        TokenBucket(1, 0)
