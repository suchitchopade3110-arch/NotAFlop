"""C4 — deep health check: per-dependency status/latency, overall status
rollup, caching, and no-cascading-failure guarantee."""
import asyncio

import pytest

from services import health


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class _FakeAsyncClient:
    """Every GET succeeds with 200 unless the target URL is in
    `_broken_hosts` (raises) or `_status_overrides` (returns that code)."""

    _broken_hosts: set = set()
    _status_overrides: dict = {}
    calls: list = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        type(self).calls.append(url)
        for host in type(self)._broken_hosts:
            if host in url:
                raise ConnectionError(f"unreachable: {url}")
        for host, code in type(self)._status_overrides.items():
            if host in url:
                return _FakeResponse(code)
        return _FakeResponse(200)


class _FakeRedisClient:
    fails = False

    async def ping(self):
        if type(self).fails:
            raise ConnectionError("redis down")
        return True


class _FakeMongoDB:
    fails = False

    async def command(self, name):
        if type(self).fails:
            raise ConnectionError("mongo down")
        return {"ok": 1}


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    health._cached_result = None
    health._cached_at = 0.0

    _FakeAsyncClient._broken_hosts = set()
    _FakeAsyncClient._status_overrides = {}
    _FakeAsyncClient.calls = []
    _FakeRedisClient.fails = False
    _FakeMongoDB.fails = False

    monkeypatch.setattr(health, "GROQ_API_KEY", "fake-key")
    monkeypatch.setattr(health.httpx, "AsyncClient", _FakeAsyncClient)

    async def _fake_get_client():
        return _FakeRedisClient()
    monkeypatch.setattr(health.cache, "get_client", _fake_get_client)
    monkeypatch.setattr(health.mongo, "get_db", lambda: _FakeMongoDB())

    monkeypatch.setattr(health.google_trends, "APIFY_API_KEY", "key")
    monkeypatch.setattr(health.product_hunt, "PH_API_KEY", "key")
    monkeypatch.setattr(health.reddit, "REDDIT_CLIENT_ID", "id")
    monkeypatch.setattr(health.reddit, "REDDIT_CLIENT_SECRET", "secret")
    yield


async def test_all_healthy_reports_degraded_because_wellfound_has_no_live_impl():
    """Honest, not a bug: per the B1 audit, wellfound has no live scraper
    at all yet, so it's always reported down — 'ok' is unreachable until
    that's implemented, and the health check must not hide that."""
    result = await health.get_health(use_cache=False)
    assert result["status"] == "degraded"
    for name, check in result["checks"].items():
        assert "latency_ms" in check
        if name == "wellfound":
            assert check["status"] == "down"
        else:
            assert check["status"] == "ok", f"{name} was not ok: {check}"


async def test_groq_unreachable_reports_overall_down():
    _FakeAsyncClient._broken_hosts.add("api.groq.com")
    result = await health.get_health(use_cache=False)
    assert result["checks"]["groq"]["status"] == "down"
    assert result["status"] == "down"


async def test_groq_not_configured_reports_down(monkeypatch):
    monkeypatch.setattr(health, "GROQ_API_KEY", "")
    result = await health.get_health(use_cache=False)
    assert result["checks"]["groq"]["status"] == "down"
    assert "not configured" in result["checks"]["groq"]["reason"]


async def test_mongo_down_reports_overall_degraded_not_down():
    _FakeMongoDB.fails = True
    result = await health.get_health(use_cache=False)
    assert result["checks"]["mongodb"]["status"] == "down"
    assert result["status"] == "degraded"  # groq is fine -> app still usable


async def test_redis_down_is_degraded():
    _FakeRedisClient.fails = True
    result = await health.get_health(use_cache=False)
    assert result["checks"]["redis"]["status"] == "down"
    assert result["status"] == "degraded"


async def test_one_data_source_unreachable_does_not_affect_others():
    """Never cascading: hacker_news failing must not flip reddit/product_hunt."""
    _FakeAsyncClient._broken_hosts.add("hn.algolia.com")
    result = await health.get_health(use_cache=False)
    assert result["checks"]["hacker_news"]["status"] == "down"
    assert result["checks"]["reddit"]["status"] == "ok"
    assert result["checks"]["product_hunt"]["status"] == "ok"
    assert result["status"] == "degraded"


async def test_unconfigured_source_reports_down_without_network_call():
    health._cached_result = None
    async def _fail(*a, **kw):
        raise AssertionError("should never issue a network call for an unconfigured source")

    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(health.reddit, "REDDIT_CLIENT_ID", "")
        mp.setattr(health.reddit, "REDDIT_CLIENT_SECRET", "")
        result = await health.get_health(use_cache=False)

    assert result["checks"]["reddit"]["status"] == "down"
    assert "not configured" in result["checks"]["reddit"]["reason"]
    assert not any("reddit.com" in url for url in _FakeAsyncClient.calls)


async def test_wellfound_always_down_no_live_implementation():
    result = await health.get_health(use_cache=False)
    assert result["checks"]["wellfound"]["status"] == "down"
    assert "no live implementation" in result["checks"]["wellfound"]["reason"]


async def test_check_timeout_reports_down_not_raise(monkeypatch):
    async def _hangs(*a, **kw):
        await asyncio.sleep(999)

    monkeypatch.setattr(health, "_check_groq", lambda: _hangs())
    monkeypatch.setattr(health, "CHECK_TIMEOUT_SECONDS", 0.05)
    result = await health.get_health(use_cache=False)
    assert result["checks"]["groq"]["status"] == "down"
    assert "timed out" in result["checks"]["groq"]["reason"]


async def test_result_is_cached_briefly():
    first = await health.get_health()
    calls_after_first = len(_FakeAsyncClient.calls)
    assert calls_after_first > 0

    second = await health.get_health()
    assert len(_FakeAsyncClient.calls) == calls_after_first  # no new network calls
    assert second == first


async def test_cache_bypassed_when_use_cache_false():
    await health.get_health()
    calls_after_first = len(_FakeAsyncClient.calls)

    await health.get_health(use_cache=False)
    assert len(_FakeAsyncClient.calls) > calls_after_first


async def test_health_endpoint_returns_full_body(mongo_db):
    from fastapi.testclient import TestClient
    import main

    health._cached_result = None
    client = TestClient(main.app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("ok", "degraded", "down")
    assert set(body["checks"].keys()) == {
        "groq", "mongodb", "redis", "google_trends", "hacker_news", "product_hunt", "reddit", "wellfound",
    }
