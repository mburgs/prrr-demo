import json

import pytest

from hookrelay.config import Settings
from hookrelay.ratelimit.bucket import TokenBucket
from hookrelay.webhooks.dispatcher import Dispatcher, Event, Response, TransportError
from hookrelay.webhooks.signing import SIGNATURE_HEADER, verify

EVENT = Event("evt-1", "tenant-red", {"seq": 1})


class ScriptedTransport:
    """Plays back ints (status codes), Responses, or exceptions to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, body, headers):
        self.calls.append((url, body, dict(headers)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, Response):
            return outcome
        return Response(outcome)


@pytest.fixture
def sleeps():
    return []


def make(transport, sleeps, clock, rand=lambda: 0.0, **overrides):
    settings = Settings.from_dict(
        {"max_attempts": 3, "retry_delay_sec": 0.25, "retry_jitter_sec": 0.0, **overrides}
    )
    return Dispatcher(transport, settings, sleep=sleeps.append, rand=rand, clock=clock)


def test_first_attempt_success(sleeps, clock):
    transport = ScriptedTransport(200)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert result.delivered and result.attempts == 1 and result.reason == "ok"
    assert sleeps == []


def test_retries_then_succeeds_with_exponential_backoff(sleeps, clock):
    transport = ScriptedTransport(503, 502, 204)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert result.delivered and result.attempts == 3
    assert sleeps == [0.25, 0.5]


def test_gives_up_after_max_attempts(sleeps, clock):
    transport = ScriptedTransport(500, 500, 500)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert not result.delivered
    assert result.attempts == 3
    assert result.status == 500
    assert result.reason == "http_500"
    assert len(transport.calls) == 3


@pytest.mark.parametrize("status", [400, 401, 404, 410])
def test_client_errors_are_not_retried(sleeps, clock, status):
    transport = ScriptedTransport(status)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert not result.delivered
    assert result.attempts == 1
    assert result.reason == f"http_{status}"
    assert sleeps == []


def test_transport_errors_are_retried(sleeps, clock):
    transport = ScriptedTransport(TransportError("boom"), 200)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert result.delivered and result.attempts == 2


def test_429_honors_retry_after(sleeps, clock):
    transport = ScriptedTransport(Response(429, {"Retry-After": "2"}), 200)
    result = make(transport, sleeps, clock).deliver(EVENT)
    assert result.delivered and result.attempts == 2
    assert sleeps == [2.0]


def test_retry_after_header_name_is_case_insensitive(sleeps, clock):
    transport = ScriptedTransport(Response(503, {"retry-after": "1"}), 200)
    make(transport, sleeps, clock).deliver(EVENT)
    assert sleeps == [1.0]


def test_retry_after_is_capped_by_max_delay(sleeps, clock):
    transport = ScriptedTransport(Response(429, {"Retry-After": "600"}), 200)
    make(transport, sleeps, clock, retry_max_delay_sec=4.0).deliver(EVENT)
    assert sleeps == [4.0]


def test_unparseable_retry_after_falls_back_to_backoff(sleeps, clock):
    date = "Wed, 21 Oct 2026 07:28:00 GMT"
    transport = ScriptedTransport(Response(429, {"Retry-After": date}), 200)
    make(transport, sleeps, clock).deliver(EVENT)
    assert sleeps == [0.25]


def test_backoff_doubles_and_is_capped(sleeps, clock):
    transport = ScriptedTransport(*[500] * 6)
    make(
        transport,
        sleeps,
        clock,
        max_attempts=6,
        retry_delay_sec=1.0,
        retry_max_delay_sec=4.0,
    ).deliver(EVENT)
    assert sleeps == [1.0, 2.0, 4.0, 4.0, 4.0]


def test_jitter_is_added_to_backoff(sleeps, clock):
    transport = ScriptedTransport(500, 200)
    make(
        transport, sleeps, clock, rand=lambda: 0.5, retry_jitter_sec=0.4
    ).deliver(EVENT)
    assert sleeps == [pytest.approx(0.25 + 0.2)]


def test_request_is_signed(sleeps, clock):
    transport = ScriptedTransport(200)
    make(transport, sleeps, clock, secret="abc").deliver(EVENT)
    url, body, headers = transport.calls[0]
    assert url == "https://hooks.example.com/ingest"
    assert json.loads(body) == {"seq": 1}
    assert verify("abc", body, headers[SIGNATURE_HEADER])


def test_global_bucket_limits_all_tenants(sleeps, clock):
    transport = ScriptedTransport(200, 200)
    bucket = TokenBucket(2, 0.001, clock)
    dispatcher = Dispatcher(
        transport, Settings(), bucket=bucket, sleep=sleeps.append, clock=clock
    )
    events = [Event(f"e{i}", f"tenant-{i}", {"seq": i}) for i in range(3)]
    results = [dispatcher.deliver(e) for e in events]
    assert [r.delivered for r in results] == [True, True, False]
    assert results[2].reason == "rate_limited"
    assert results[2].attempts == 0
    assert results[2].retry_after == pytest.approx(1000.0)
    assert len(transport.calls) == 2


def test_tenant_limit_does_not_affect_other_tenants(sleeps, clock):
    transport = ScriptedTransport(*[200] * 10)
    settings = Settings.from_dict({"tenant_capacity": 2, "tenant_refill_per_sec": 1.0})
    dispatcher = Dispatcher(transport, settings, sleep=sleeps.append, clock=clock)
    red = [dispatcher.deliver(Event(f"r{i}", "red", {"seq": i})) for i in range(3)]
    blue = dispatcher.deliver(Event("b0", "blue", {"seq": 9}))
    assert [r.delivered for r in red] == [True, True, False]
    assert red[2].reason == "tenant_rate_limited"
    assert red[2].retry_after == pytest.approx(1.0)
    assert blue.delivered
    assert len(transport.calls) == 3


def test_tenant_recovers_after_waiting(sleeps, clock):
    transport = ScriptedTransport(*[200] * 10)
    settings = Settings.from_dict({"tenant_capacity": 2, "tenant_refill_per_sec": 1.0})
    dispatcher = Dispatcher(transport, settings, sleep=sleeps.append, clock=clock)
    for i in range(2):
        dispatcher.deliver(Event(f"r{i}", "red", {"seq": i}))
    third = Event("r2", "red", {"seq": 2})
    limited = dispatcher.deliver(third)
    clock.advance(limited.retry_after)
    assert dispatcher.deliver(third).delivered
