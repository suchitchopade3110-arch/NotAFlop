import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.specialist_agents import ALL_AGENTS
from core.session import SESSION_HEADER
from models.documents import AgentResultRecord, ReportDocument
from orchestrator.state import AgentOutput
from repositories import report_repository
from routers import v1_ideas
from services import snapshot_worker

app = FastAPI()
app.include_router(v1_ideas.router, prefix="/v1")
client = TestClient(app)


def _make_report(public_id="rep0000001", session_id="sess1") -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id=session_id,
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        signals={"reddit": {"status": "ok", "post_count": 5}},
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"),
            "timing": AgentResultRecord(agent="timing", passed=True, score=6, evidence="e", feedback="f", model="m"),
        },
        weights_version=2,
        raw_score=75,
        verdict="go",
    )


def _promote(session_id="sess1", public_id="rep0000001") -> dict:
    report = _make_report(public_id=public_id, session_id=session_id)

    async def _seed():
        await report_repository.create_report(report)

    import asyncio
    asyncio.run(_seed())

    res = client.post("/v1/ideas", json={"report_id": public_id}, headers={SESSION_HEADER: session_id})
    assert res.status_code == 201, res.text
    return res.json()


def test_promote_idea_success(mongo_db):
    body = _promote()
    assert body["raw_score"] == 75
    assert body["verdict"] == "go"
    assert body["share_token"]


def test_promote_idea_report_not_found(mongo_db):
    res = client.post("/v1/ideas", json={"report_id": "nope"}, headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 404


def test_promote_idea_wrong_session_rejected(mongo_db):
    report = _make_report(session_id="owner-session")

    async def _seed():
        await report_repository.create_report(report)

    import asyncio
    asyncio.run(_seed())

    res = client.post(
        "/v1/ideas", json={"report_id": "rep0000001"}, headers={SESSION_HEADER: "other-session"}
    )
    assert res.status_code == 404


def test_list_ideas_owned_only(mongo_db):
    _promote(session_id="sess1", public_id="rep0000001")
    res = client.get("/v1/ideas", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    other = client.get("/v1/ideas", headers={SESSION_HEADER: "sess-other"})
    assert other.json() == []


def test_get_idea_not_owned_returns_404(mongo_db):
    body = _promote(session_id="sess1")
    res = client.get(f"/v1/ideas/{body['idea_id']}", headers={SESSION_HEADER: "sess-other"})
    assert res.status_code == 404


def test_get_idea_owned(mongo_db):
    body = _promote(session_id="sess1")
    res = client.get(f"/v1/ideas/{body['idea_id']}", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    assert res.json()["idea_id"] == body["idea_id"]


def test_delete_idea_cascade(mongo_db):
    body = _promote(session_id="sess1")
    res = client.delete(f"/v1/ideas/{body['idea_id']}", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 204

    res2 = client.get(f"/v1/ideas/{body['idea_id']}", headers={SESSION_HEADER: "sess1"})
    assert res2.status_code == 404


def test_list_snapshots_initial_only(mongo_db):
    body = _promote(session_id="sess1")
    res = client.get(f"/v1/ideas/{body['idea_id']}/snapshots", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    snapshots = res.json()
    assert len(snapshots) == 1
    assert snapshots[0]["trigger"] == "initial"


def test_force_snapshot_success(mongo_db, monkeypatch):
    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {"reddit": {"status": "ok", "post_count": 5}}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=7, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)

    body = _promote(session_id="sess1")
    res = client.post(f"/v1/ideas/{body['idea_id']}/snapshots", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 201, res.text
    assert res.json()["trigger"] == "manual"


def test_force_snapshot_rate_limited(mongo_db, monkeypatch, fake_redis):
    from services import rate_limiter

    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(rate_limiter, "get_client", _fake_get_client)
    monkeypatch.setattr("core.config.SNAPSHOT_MANUAL_RERUN_MAX", 1)
    monkeypatch.setattr(rate_limiter, "SNAPSHOT_MANUAL_RERUN_MAX", 1)

    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=7, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)

    body = _promote(session_id="sess1")
    first = client.post(f"/v1/ideas/{body['idea_id']}/snapshots", headers={SESSION_HEADER: "sess1"})
    assert first.status_code == 201
    second = client.post(f"/v1/ideas/{body['idea_id']}/snapshots", headers={SESSION_HEADER: "sess1"})
    assert second.status_code == 429


def test_timeline_includes_initial_snapshot(mongo_db):
    body = _promote(session_id="sess1")
    res = client.get(f"/v1/ideas/{body['idea_id']}/timeline", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    assert entries[0]["type"] == "snapshot"
