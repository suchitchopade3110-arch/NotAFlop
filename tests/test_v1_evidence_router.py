import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.specialist_agents import ALL_AGENTS
from core.session import SESSION_HEADER
from models.documents import AgentResultRecord, ReportDocument
from orchestrator.state import AgentOutput
from repositories import report_repository
from routers import v1_evidence
from services import log_service, snapshot_worker

app = FastAPI()
app.include_router(v1_evidence.router, prefix="/v1")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=7, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


def _promote(session_id="sess1") -> str:
    report = ReportDocument(
        public_id="rep0000001",
        session_id=session_id,
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=6, evidence="e", feedback="f", model="m"),
        },
        weights_version=2,
        raw_score=60,
        verdict="pivot",
    )

    async def _seed():
        await report_repository.create_report(report)
        return await log_service.promote_report_to_idea(
            report, session_id=session_id, account_id=None, share_token="tok_ev_router"
        )

    idea = asyncio.run(_seed())
    return idea.idea_id


def test_submit_evidence_success(mongo_db):
    idea_id = _promote()
    res = client.post(
        f"/v1/ideas/{idea_id}/evidence",
        json={"type": "waitlist", "payload": {"count": 100}},
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "waitlist"
    assert body["snapshot"]["trigger"] == "evidence"


def test_submit_evidence_empty_payload_rejected(mongo_db):
    idea_id = _promote()
    res = client.post(
        f"/v1/ideas/{idea_id}/evidence",
        json={"type": "waitlist", "payload": {}},
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 422


def test_submit_evidence_not_owned_404(mongo_db):
    idea_id = _promote(session_id="sess1")
    res = client.post(
        f"/v1/ideas/{idea_id}/evidence",
        json={"type": "waitlist", "payload": {"count": 1}},
        headers={SESSION_HEADER: "someone-else"},
    )
    assert res.status_code == 404


def test_list_milestones_seeds_on_first_call(mongo_db):
    idea_id = _promote()
    res = client.get(f"/v1/ideas/{idea_id}/milestones", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    milestones = res.json()
    assert len(milestones) == 3
    assert all(m["completed"] is False for m in milestones)


def test_patch_milestone_completes_it(mongo_db):
    idea_id = _promote()
    milestones = client.get(f"/v1/ideas/{idea_id}/milestones", headers={SESSION_HEADER: "sess1"}).json()
    mid = milestones[0]["milestone_id"]

    res = client.patch(f"/v1/milestones/{mid}", json={"completed": True}, headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200, res.text
    assert res.json()["completed"] is True
    assert res.json()["completed_at"] is not None


def test_patch_milestone_not_owned_404(mongo_db):
    idea_id = _promote(session_id="sess1")
    milestones = client.get(f"/v1/ideas/{idea_id}/milestones", headers={SESSION_HEADER: "sess1"}).json()
    mid = milestones[0]["milestone_id"]

    res = client.patch(
        f"/v1/milestones/{mid}", json={"completed": True}, headers={SESSION_HEADER: "someone-else"}
    )
    assert res.status_code == 404


def test_patch_milestone_with_mismatched_evidence_rejected(mongo_db):
    idea_id = _promote()
    milestones = client.get(f"/v1/ideas/{idea_id}/milestones", headers={SESSION_HEADER: "sess1"}).json()
    mid = milestones[0]["milestone_id"]

    res = client.patch(
        f"/v1/milestones/{mid}",
        json={"completed": True, "evidence_id": "ev_does_not_exist"},
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 400
