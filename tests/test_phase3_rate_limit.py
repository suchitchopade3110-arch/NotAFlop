import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.specialist_agents import ALL_AGENTS
from core.config import RATE_LIMIT_SESSION_MAX
from core.session import SESSION_HEADER
from orchestrator.state import AgentOutput
from routers import phase3
from services import rate_limiter

app = FastAPI()
app.include_router(phase3.router, prefix="/api/phase3")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _patch_agents(monkeypatch):
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=8, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state(monkeypatch, fake_redis):
    monkeypatch.setattr(rate_limiter, "_redis_available", True)
    monkeypatch.setattr(rate_limiter, "_memory_store", {})

    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(rate_limiter, "get_client", _fake_get_client)


def _analyze(session_id: str | None = None):
    headers = {SESSION_HEADER: session_id} if session_id else {}
    return client.post(
        "/api/phase3/analyze",
        json={"transcript": "Uber for dogs", "keyword": "dog walking", "signals": {}},
        headers=headers,
    )


def test_allows_requests_under_session_quota(mongo_db):
    for _ in range(RATE_LIMIT_SESSION_MAX):
        res = _analyze(session_id="quota-session")
        assert res.status_code == 200
        assert SESSION_HEADER in res.headers


def test_blocks_with_429_after_session_quota_exceeded(mongo_db):
    for _ in range(RATE_LIMIT_SESSION_MAX):
        assert _analyze(session_id="quota-session-2").status_code == 200

    res = _analyze(session_id="quota-session-2")
    assert res.status_code == 429
    body = res.json()["detail"]
    assert body["scope"] == "session"
    assert body["limit"] == RATE_LIMIT_SESSION_MAX
    assert body["remaining"] == 0
    assert "reset_at" in body


def test_mints_session_id_when_absent(mongo_db):
    res = _analyze(session_id=None)
    assert res.status_code == 200
    assert res.headers[SESSION_HEADER]  # non-empty, server-minted
