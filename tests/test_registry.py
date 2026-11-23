import pytest

from hookrelay.config import Settings
from hookrelay.ratelimit.registry import TenantRegistry


def make(clock, capacity=2, refill=1.0, max_tenants=3):
    return TenantRegistry(capacity, refill, max_tenants, clock)


def test_tenants_have_independent_buckets(clock):
    reg = make(clock)
    assert reg.allow("a") and reg.allow("a")
    assert not reg.allow("a")
    assert reg.allow("b")


def test_bucket_refills_per_tenant(clock):
    reg = make(clock, capacity=4, refill=2.0)
    for _ in range(4):
        reg.allow("a")
    clock.advance(1)
    assert reg.allow("a") and reg.allow("a")
    assert not reg.allow("a")


def test_evicts_least_recently_used(clock):
    reg = make(clock, max_tenants=2)
    reg.allow("a")
    reg.allow("b")
    reg.allow("c")
    assert "a" not in reg
    assert "b" in reg and "c" in reg
    assert len(reg) == 2


def test_use_refreshes_recency(clock):
    reg = make(clock, max_tenants=2)
    reg.allow("a")
    reg.allow("b")
    reg.allow("a")
    reg.allow("c")
    assert "b" not in reg
    assert "a" in reg


def test_evicted_tenant_returns_with_full_bucket(clock):
    reg = make(clock, max_tenants=1)
    reg.allow("a")
    reg.allow("a")
    assert not reg.allow("a")
    reg.allow("b")
    assert reg.allow("a")


def test_remaining_and_retry_after_do_not_create_buckets(clock):
    reg = make(clock)
    assert reg.remaining("ghost") == 2
    assert reg.retry_after("ghost") == 0.0
    assert len(reg) == 0


def test_retry_after_for_drained_tenant(clock):
    reg = make(clock, refill=4.0)
    reg.allow("a")
    reg.allow("a")
    assert reg.retry_after("a") == pytest.approx(0.25)


def test_snapshot_is_ordered_by_recency(clock):
    reg = make(clock)
    reg.allow("a")
    reg.allow("b")
    reg.allow("a")
    assert list(reg.snapshot()) == ["b", "a"]
    assert reg.snapshot()["a"] == pytest.approx(0.0)


def test_from_settings(clock):
    settings = Settings.from_dict(
        {"tenant_capacity": 7, "tenant_refill_per_sec": 2.0, "max_tenants": 5}
    )
    reg = TenantRegistry.from_settings(settings, clock)
    assert reg.capacity == 7
    assert reg.remaining("x") == 7


def test_rejects_zero_max_tenants(clock):
    with pytest.raises(ValueError):
        make(clock, max_tenants=0)
