import dataclasses

import pytest

from hookrelay.config import Settings


def test_defaults():
    s = Settings()
    assert s.retry_count == 3
    assert s.bucket_capacity == 10


def test_from_dict_overrides():
    s = Settings.from_dict({"retry_count": 5, "secret": "x"})
    assert s.retry_count == 5
    assert s.secret == "x"
    assert s.timeout_sec == 5.0


def test_unknown_keys_rejected():
    with pytest.raises(ValueError, match="bogus"):
        Settings.from_dict({"bogus": 1})


def test_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Settings().retry_count = 9  # type: ignore[misc]
