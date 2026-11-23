import pytest

from hookrelay.webhooks.signing import sign, sign_legacy, verify

BODY = b'{"seq": 1}'
T0 = 1_700_000_000


def test_sign_format_is_timestamped():
    sig = sign("s3cret", BODY, timestamp=T0)
    prefix, _, digest = sig.partition(",v1=")
    assert prefix == f"t={T0}"
    assert len(digest) == 64
    int(digest, 16)


def test_sign_is_deterministic_for_a_timestamp():
    assert sign("s3cret", BODY, T0) == sign("s3cret", BODY, T0)
    assert sign("s3cret", BODY, T0) != sign("s3cret", BODY, T0 + 1)


def test_verify_round_trip():
    assert verify("s3cret", BODY, sign("s3cret", BODY, T0), now=T0 + 1)


def test_verify_uses_current_time_by_default():
    assert verify("s3cret", BODY, sign("s3cret", BODY))


def test_verify_rejects_wrong_secret():
    assert not verify("other", BODY, sign("s3cret", BODY, T0), now=T0)


def test_verify_rejects_tampered_body():
    assert not verify("s3cret", b'{"seq": 2}', sign("s3cret", BODY, T0), now=T0)


def test_verify_rejects_rewritten_timestamp():
    digest = sign("s3cret", BODY, T0).split("v1=")[1]
    assert not verify("s3cret", BODY, f"t={T0 + 10},v1={digest}", now=T0 + 10)


def test_stale_signature_is_rejected():
    sig = sign("s3cret", BODY, T0)
    assert verify("s3cret", BODY, sig, now=T0 + 300)
    assert not verify("s3cret", BODY, sig, now=T0 + 301)


def test_future_signature_is_rejected():
    sig = sign("s3cret", BODY, T0 + 1000)
    assert not verify("s3cret", BODY, sig, now=T0)


def test_custom_tolerance():
    sig = sign("s3cret", BODY, T0)
    assert verify("s3cret", BODY, sig, now=T0 + 30, tolerance_sec=60)
    assert not verify("s3cret", BODY, sig, now=T0 + 90, tolerance_sec=60)


@pytest.mark.parametrize(
    "bad",
    ["", "t=abc,v1=00", "t=1", "v1=00", "t=1,v1", "garbage=", "t=1,,v1=00"],
)
def test_malformed_signatures_are_rejected(bad):
    assert not verify("s3cret", BODY, bad, now=T0)


def test_non_ascii_signature_does_not_raise():
    assert not verify("s3cret", BODY, "t=1,v1=\u00e9", now=1)
    assert not verify("s3cret", BODY, "\u00e9\u00e9", now=1)


def test_legacy_signature_is_still_accepted():
    assert verify("s3cret", BODY, sign_legacy("s3cret", BODY))


def test_legacy_signature_still_checks_body_and_secret():
    legacy = sign_legacy("s3cret", BODY)
    assert not verify("s3cret", b"other", legacy)
    assert not verify("nope", BODY, legacy)


def test_bytes_and_str_secrets_match():
    assert sign("s3cret", BODY, T0) == sign(b"s3cret", BODY, T0)
