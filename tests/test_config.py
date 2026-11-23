import dataclasses

import pytest

from hookrelay.config import Settings


def test_defaults():
    s = Settings()
    assert s.max_attempts == 3
    assert s.bucket_capacity == 10
    assert s.tenant_capacity == 3
    assert s.tenant_refill_per_sec == 1.0
    assert s.max_tenants == 1000


def test_from_dict_overrides():
    s = Settings.from_dict({"max_attempts": 5, "secret": "x"})
    assert s.max_attempts == 5
    assert s.secret == "x"
    assert s.timeout_sec == 5.0


def test_unknown_keys_rejected():
    with pytest.raises(ValueError, match="bogus"):
        Settings.from_dict({"bogus": 1})


def test_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Settings().max_attempts = 9  # type: ignore[misc]


def test_old_retry_count_key_is_rejected():
    with pytest.raises(ValueError, match="retry_count"):
        Settings.from_dict({"retry_count": 3})
