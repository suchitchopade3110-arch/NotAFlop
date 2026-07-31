import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from core.config import RATE_LIMIT_IP_MAX, RATE_LIMIT_SESSION_MAX
from services import rate_limiter


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, fake_redis):
    monkeypatch.setattr(rate_limiter, "_redis_available", True)
    monkeypatch.setattr(rate_limiter, "_memory_store", {})

    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(rate_limiter, "get_client", _fake_get_client)
    yield


async def test_session_cap_allows_up_to_limit():
    for i in range(RATE_LIMIT_SESSION_MAX):
        result = await rate_limiter.check_rate_limit(session_id="s1", ip="1.1.1.1")
        assert result.allowed is True, f"call {i} should be allowed"


async def test_session_cap_blocks_after_limit():
    for _ in range(RATE_LIMIT_SESSION_MAX):
        await rate_limiter.check_rate_limit(session_id="s1", ip="1.1.1.1")

    blocked = await rate_limiter.check_rate_limit(session_id="s1", ip="1.1.1.1")
    assert blocked.allowed is False
    assert blocked.scope == "session"
    assert blocked.limit == RATE_LIMIT_SESSION_MAX
    assert blocked.remaining == 0


async def test_remaining_decrements_correctly():
    r1 = await rate_limiter.check_rate_limit(session_id="s2", ip="2.2.2.2")
    assert r1.remaining == RATE_LIMIT_SESSION_MAX - 1
    r2 = await rate_limiter.check_rate_limit(session_id="s2", ip="2.2.2.2")
    assert r2.remaining == RATE_LIMIT_SESSION_MAX - 2


async def test_different_sessions_have_independent_session_quota():
    for _ in range(RATE_LIMIT_SESSION_MAX):
        await rate_limiter.check_rate_limit(session_id="s3", ip="3.3.3.3")

    # A different session, same IP, still has its own session quota.
    result = await rate_limiter.check_rate_limit(session_id="s4", ip="3.3.3.3")
    assert result.allowed is True


async def test_ip_cap_blocks_across_many_sessions_same_ip():
    # Cycle through more distinct sessions than the IP cap allows — each
    # session's first request is under its own session cap, so the IP
    # cap is what should eventually trip.
    allowed_count = 0
    for i in range(RATE_LIMIT_IP_MAX + 3):
        result = await rate_limiter.check_rate_limit(session_id=f"session-{i}", ip="9.9.9.9")
        if result.allowed:
            allowed_count += 1
        else:
            assert result.scope == "ip"

    assert allowed_count == RATE_LIMIT_IP_MAX


async def test_falls_back_to_memory_on_redis_error(monkeypatch):
    async def _broken_client():
        raise RedisConnectionError("no redis")

    monkeypatch.setattr(rate_limiter, "get_client", _broken_client)

    result = await rate_limiter.check_rate_limit(session_id="s5", ip="5.5.5.5")
    assert result.allowed is True
    assert rate_limiter._redis_available is False

    # Limit is still enforced, just via the in-memory fallback now.
    for _ in range(RATE_LIMIT_SESSION_MAX - 1):
        await rate_limiter.check_rate_limit(session_id="s5", ip="5.5.5.5")
    blocked = await rate_limiter.check_rate_limit(session_id="s5", ip="5.5.5.5")
    assert blocked.allowed is False


async def test_fails_open_on_unexpected_error(monkeypatch):
    def _broken_memory(*args, **kwargs):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(rate_limiter, "_redis_available", False)
    monkeypatch.setattr(rate_limiter, "_count_and_record_memory", _broken_memory)

    result = await rate_limiter.check_rate_limit(session_id="s6", ip="6.6.6.6")
    assert result.allowed is True
