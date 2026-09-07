import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.documents import AgentResultRecord, ReportDocument
from repositories import report_repository
from routers import v1_share
from services import log_service, rate_limiter

app = FastAPI()
app.include_router(v1_share.router, prefix="/v1")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter(monkeypatch, fake_redis):
    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(rate_limiter, "get_client", _fake_get_client)


def _promote(mongo_db) -> str:
    report = ReportDocument(
        public_id="rep0000001",
        session_id="sess1",
        idea_hash="hash1",
        transcript="Uber for dog walking — the secret sauce nobody should see",
        keyword="dog walking",
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=9, evidence="e", feedback="f", model="m"),
            "timing": AgentResultRecord(agent="timing", passed=True, score=3, evidence="e", feedback="f", model="m"),
        },
        weights_version=2,
        raw_score=75,
        verdict="go",
    )

    async def _seed():
        await report_repository.create_report(report)
        return await log_service.promote_report_to_idea(
            report, session_id="sess1", account_id=None, share_token="tok_share1"
        )

    idea = asyncio.run(_seed())
    return idea.share_token


def test_share_card_returns_verdict_and_score(mongo_db):
    token = _promote(mongo_db)
    res = client.get(f"/v1/share/{token}")
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "go"
    assert body["raw_score"] == 75
    assert body["keyword"] == "dog walking"
    assert body["top_reasons"]


def test_share_card_never_leaks_pitch_text(mongo_db):
    token = _promote(mongo_db)
    res = client.get(f"/v1/share/{token}")
    body = res.json()
    assert "secret sauce" not in str(body)
    assert "transcript" not in body
    assert "session_id" not in body
    assert "email" not in body


def test_share_card_unknown_token_404(mongo_db):
    res = client.get("/v1/share/does-not-exist")
    assert res.status_code == 404


def test_share_card_deleted_idea_404(mongo_db):
    token = _promote(mongo_db)

    async def _delete():
        from repositories import idea_repository

        idea = await idea_repository.get_by_share_token(token)
        await log_service.delete_idea_cascade(idea.idea_id)

    asyncio.run(_delete())
    res = client.get(f"/v1/share/{token}")
    assert res.status_code == 404


def test_share_card_rate_limited(mongo_db, monkeypatch):
    monkeypatch.setattr(rate_limiter, "SHARE_CARD_RATE_LIMIT_MAX", 1)
    token = _promote(mongo_db)

    first = client.get(f"/v1/share/{token}")
    assert first.status_code == 200
    second = client.get(f"/v1/share/{token}")
    assert second.status_code == 429
