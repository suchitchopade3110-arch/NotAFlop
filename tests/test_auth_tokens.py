import pytest

from services import auth_tokens


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, fake_redis):
    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(auth_tokens, "get_client", _fake_get_client)
    monkeypatch.setattr(auth_tokens, "_redis_available", True)
    auth_tokens._memory_tokens.clear()
    auth_tokens._memory_rate.clear()
    yield


async def test_issue_and_redeem_token():
    token = await auth_tokens.issue_token("founder@example.com", "sess-1")
    redeemed = await auth_tokens.redeem_token(token)
    assert redeemed == {"email": "founder@example.com", "session_id": "sess-1"}


async def test_redeem_is_single_use():
    token = await auth_tokens.issue_token("founder@example.com", "sess-1")
    first = await auth_tokens.redeem_token(token)
    second = await auth_tokens.redeem_token(token)
    assert first is not None
    assert second is None


async def test_redeem_unknown_token_returns_none():
    assert await auth_tokens.redeem_token("does-not-exist") is None


async def test_rate_limit_allows_up_to_max(monkeypatch):
    # auth_tokens reads MAGIC_LINK_RATE_LIMIT_MAX as a module-level name
    # bound at import time — patch it directly on the module under test.
    monkeypatch.setattr(auth_tokens, "MAGIC_LINK_RATE_LIMIT_MAX", 3)

    results = [await auth_tokens.check_and_record_rate_limit("email", "a@example.com") for _ in range(4)]
    assert results == [True, True, True, False]


async def test_rate_limit_scoped_independently_per_key():
    for _ in range(4):
        await auth_tokens.check_and_record_rate_limit("email", "a@example.com")
    # A different email/ip key isn't affected by the first key's count.
    assert await auth_tokens.check_and_record_rate_limit("email", "b@example.com") is True


async def test_falls_back_to_memory_when_redis_unavailable(monkeypatch):
    async def _broken():
        raise ConnectionError("down")

    monkeypatch.setattr(auth_tokens, "get_client", _broken)

    token = await auth_tokens.issue_token("founder@example.com", "sess-1")
    redeemed = await auth_tokens.redeem_token(token)
    assert redeemed == {"email": "founder@example.com", "session_id": "sess-1"}

    allowed = await auth_tokens.check_and_record_rate_limit("email", "founder@example.com")
    assert allowed is True
