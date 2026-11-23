import json

import pytest

from hookrelay.config import Settings
from hookrelay.ratelimit.bucket import TokenBucket
from hookrelay.webhooks.dispatcher import Dispatcher, Event, Response, TransportError
from hookrelay.webhooks.signing import SIGNATURE_HEADER, verify

EVENT = Event("evt-1", "tenant-red", {"seq": 1})


class ScriptedTransport:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, body, headers):
        self.calls.append((url, body, dict(headers)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Response(outcome)


@pytest.fixture
def sleeps():
    return []


def make(transport, sleeps, **overrides):
    settings = Settings.from_dict({"retry_count": 3, "retry_delay_sec": 0.25, **overrides})
    return Dispatcher(transport, settings, sleep=sleeps.append)


def test_first_attempt_success(sleeps):
    transport = ScriptedTransport(200)
    result = make(transport, sleeps).deliver(EVENT)
    assert result.delivered and result.attempts == 1 and result.reason == "ok"
    assert sleeps == []


def test_retries_then_succeeds(sleeps):
    transport = ScriptedTransport(503, 502, 204)
    result = make(transport, sleeps).deliver(EVENT)
    assert result.delivered and result.attempts == 3
    assert sleeps == [0.25, 0.25]


def test_gives_up_after_retry_count(sleeps):
    transport = ScriptedTransport(500, 500, 500)
    result = make(transport, sleeps).deliver(EVENT)
    assert not result.delivered
    assert result.attempts == 3
    assert result.status == 500
    assert result.reason == "http_500"
    assert len(transport.calls) == 3


def test_transport_errors_are_retried(sleeps):
    transport = ScriptedTransport(TransportError("boom"), 200)
    result = make(transport, sleeps).deliver(EVENT)
    assert result.delivered and result.attempts == 2


def test_request_is_signed(sleeps):
    transport = ScriptedTransport(200)
    make(transport, sleeps, secret="abc").deliver(EVENT)
    url, body, headers = transport.calls[0]
    assert url == "https://hooks.example.com/ingest"
    assert json.loads(body) == {"seq": 1}
    assert verify("abc", body, headers[SIGNATURE_HEADER])


def test_rate_limited_events_never_hit_transport(sleeps):
    transport = ScriptedTransport(200, 200)
    bucket = TokenBucket(2, 0.001)
    dispatcher = Dispatcher(
        transport, Settings(), sleep=sleeps.append, bucket=bucket
    )
    results = [dispatcher.deliver(EVENT) for _ in range(3)]
    assert [r.delivered for r in results] == [True, True, False]
    assert results[2].reason == "rate_limited"
    assert results[2].attempts == 0
    assert len(transport.calls) == 2
