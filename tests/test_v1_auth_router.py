import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.session import SESSION_HEADER
from models.documents import AgentResultRecord, ReportDocument
from repositories import report_repository
from routers import v1_auth
from services import auth_tokens, log_service

app = FastAPI()
app.include_router(v1_auth.router, prefix="/v1")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_auth_state(monkeypatch, fake_redis):
    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(auth_tokens, "get_client", _fake_get_client)
    monkeypatch.setattr(auth_tokens, "_redis_available", True)
    auth_tokens._memory_tokens.clear()
    auth_tokens._memory_rate.clear()
    yield


def test_create_session_mints_new_id(mongo_db):
    res = client.post("/v1/session")
    assert res.status_code == 200
    body = res.json()
    assert body["session_id"]
    assert res.headers[SESSION_HEADER] == body["session_id"]


def test_create_session_echoes_supplied_id(mongo_db):
    res = client.post("/v1/session", headers={SESSION_HEADER: "sess-fixed"})
    assert res.json()["session_id"] == "sess-fixed"


def test_claim_rejects_invalid_email(mongo_db):
    res = client.post("/v1/auth/claim", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_claim_then_verify_binds_session_to_account(mongo_db, monkeypatch):
    captured = {}

    def _fake_info(event, **kwargs):
        if event == "magic_link_issued":
            captured.update(kwargs)

    monkeypatch.setattr(v1_auth.logger, "info", _fake_info)

    claim_res = client.post(
        "/v1/auth/claim", json={"email": "founder@example.com"}, headers={SESSION_HEADER: "sess-claim"}
    )
    assert claim_res.status_code == 200
    assert claim_res.json() == {"status": "sent"}
    assert "link" in captured

    token = captured["link"].split("token=")[1]

    verify_res = client.post("/v1/auth/verify", json={"token": token})
    assert verify_res.status_code == 200
    body = verify_res.json()
    assert body["email"] == "founder@example.com"
    assert body["session_id"] == "sess-claim"
    assert body["claimed_ideas"] == 0

    # Token is single-use.
    replay = client.post("/v1/auth/verify", json={"token": token})
    assert replay.status_code == 400


def test_verify_invalid_token_rejected(mongo_db):
    res = client.post("/v1/auth/verify", json={"token": "garbage"})
    assert res.status_code == 400


def test_verify_transfers_owned_ideas(mongo_db, monkeypatch):
    report = ReportDocument(
        public_id="rep0000001",
        session_id="sess-owner",
        idea_hash="h1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={"problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m")},
        weights_version=2,
        raw_score=75,
        verdict="go",
    )

    async def _seed():
        await report_repository.create_report(report)
        return await log_service.promote_report_to_idea(
            report, session_id="sess-owner", account_id=None, share_token="tok_owner"
        )

    import asyncio

    idea = asyncio.run(_seed())
    assert idea is not None

    captured = {}
    monkeypatch.setattr(
        v1_auth.logger, "info", lambda event, **kw: captured.update(kw) if event == "magic_link_issued" else None
    )

    client.post("/v1/auth/claim", json={"email": "owner@example.com"}, headers={SESSION_HEADER: "sess-owner"})
    token = captured["link"].split("token=")[1]

    res = client.post("/v1/auth/verify", json={"token": token})
    assert res.json()["claimed_ideas"] == 1


def test_me_anonymous(mongo_db):
    res = client.get("/v1/me", headers={SESSION_HEADER: "sess-anon"})
    assert res.status_code == 200
    body = res.json()
    assert body["account_id"] is None
    assert body["email"] is None
    assert body["owned_idea_count"] == 0


def test_me_after_claim(mongo_db, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        v1_auth.logger, "info", lambda event, **kw: captured.update(kw) if event == "magic_link_issued" else None
    )
    client.post("/v1/session", headers={SESSION_HEADER: "sess-me"})
    client.post("/v1/auth/claim", json={"email": "me@example.com"}, headers={SESSION_HEADER: "sess-me"})
    token = captured["link"].split("token=")[1]
    client.post("/v1/auth/verify", json={"token": token})

    res = client.get("/v1/me", headers={SESSION_HEADER: "sess-me"})
    body = res.json()
    assert body["account_id"] is not None
    assert body["email"] == "me@example.com"


def test_claim_rate_limited(mongo_db, monkeypatch):
    monkeypatch.setattr(auth_tokens, "MAGIC_LINK_RATE_LIMIT_MAX", 1)
    monkeypatch.setattr(v1_auth.logger, "info", lambda *a, **k: None)

    first = client.post("/v1/auth/claim", json={"email": "rl@example.com"}, headers={SESSION_HEADER: "sess-rl"})
    assert first.status_code == 200
    second = client.post("/v1/auth/claim", json={"email": "rl@example.com"}, headers={SESSION_HEADER: "sess-rl2"})
    assert second.status_code == 429
