import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config as core_config
from core import dependencies
from models.documents import AgentResultRecord, ReportDocument
from repositories import report_repository
from routers import internal
from services import log_service
from services.gate import WEIGHTS_VERSION

app = FastAPI()
app.include_router(internal.router, prefix="/internal")
client = TestClient(app)


def _promote(session_id="sess1", public_id="rep0000001") -> str:
    report = ReportDocument(
        public_id=public_id,
        session_id=session_id,
        idea_hash=f"hash-{public_id}",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"),
        },
        weights_version=WEIGHTS_VERSION,
        raw_score=70,
        verdict="go",
    )

    async def _seed():
        await report_repository.create_report(report)
        return await log_service.promote_report_to_idea(
            report, session_id=session_id, account_id=None, share_token=f"tok_{public_id}"
        )

    idea = asyncio.run(_seed())
    return idea.idea_id


def test_rescore_requires_admin_key(mongo_db, monkeypatch):
    monkeypatch.setattr(core_config, "ADMIN_API_KEY", "secret-key")
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")

    res = client.post("/internal/rescore", json={})
    assert res.status_code == 401


def test_rescore_single_idea_skipped_when_current(mongo_db, monkeypatch):
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    idea_id = _promote()

    res = client.post(
        "/internal/rescore", json={"idea_id": idea_id}, headers={"X-Admin-Key": "secret-key"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["weights_version"] == WEIGHTS_VERSION
    assert body["results"] == [{"idea_id": idea_id, "snapshot_id": None, "status": "skipped_no_change"}]


def test_rescore_single_idea_not_found(mongo_db, monkeypatch):
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    res = client.post(
        "/internal/rescore", json={"idea_id": "idea_does_not_exist"}, headers={"X-Admin-Key": "secret-key"}
    )
    assert res.status_code == 404


def test_rescore_sweep_all_ideas(mongo_db, monkeypatch):
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    idea1 = _promote(session_id="sess1", public_id="rep0000001")
    idea2 = _promote(session_id="sess2", public_id="rep0000002")

    res = client.post("/internal/rescore", json={}, headers={"X-Admin-Key": "secret-key"})
    assert res.status_code == 200
    ids = {r["idea_id"] for r in res.json()["results"]}
    assert ids == {idea1, idea2}


def test_rescore_actually_moves_a_stale_idea(mongo_db, monkeypatch):
    import services.log_service as ls
    import services.rescore_service as rs

    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    idea_id = _promote()

    monkeypatch.setattr(ls, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    monkeypatch.setattr(rs, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    monkeypatch.setattr(internal, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)

    res = client.post(
        "/internal/rescore", json={"idea_id": idea_id}, headers={"X-Admin-Key": "secret-key"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["weights_version"] == WEIGHTS_VERSION + 1
    assert body["results"][0]["status"] == "rescored"
    assert body["results"][0]["snapshot_id"] is not None
