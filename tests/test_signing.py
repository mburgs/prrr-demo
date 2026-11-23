from hookrelay.webhooks.signing import sign, verify

BODY = b'{"seq": 1}'


def test_sign_is_deterministic_hex():
    sig = sign("s3cret", BODY)
    assert sig == sign("s3cret", BODY)
    assert len(sig) == 64
    int(sig, 16)


def test_verify_round_trip():
    assert verify("s3cret", BODY, sign("s3cret", BODY))


def test_verify_rejects_wrong_secret():
    assert not verify("other", BODY, sign("s3cret", BODY))


def test_verify_rejects_tampered_body():
    assert not verify("s3cret", b'{"seq": 2}', sign("s3cret", BODY))


def test_bytes_and_str_secrets_match():
    assert sign("s3cret", BODY) == sign(b"s3cret", BODY)
