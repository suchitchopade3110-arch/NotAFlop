import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.specialist_agents import ALL_AGENTS
from core.session import SESSION_HEADER
from models.documents import AgentResultRecord, ReportDocument
from orchestrator.state import AgentOutput
from repositories import report_repository
from routers import v1_criteria
from services import log_service, snapshot_worker

app = FastAPI()
app.include_router(v1_criteria.router, prefix="/v1")
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
            report, session_id=session_id, account_id=None, share_token="tok_crit_router"
        )

    idea = asyncio.run(_seed())
    return idea.idea_id


def _future_iso(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_create_criterion_success(mongo_db):
    idea_id = _promote()
    res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "If fewer than 10/30 vets reply positively, pivot.",
            "metric": "positive replies",
            "threshold": ">= 10 of 30",
            "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "pending"


def test_create_criterion_vague_rejected(mongo_db):
    idea_id = _promote()
    res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={"statement": "x", "metric": "y", "threshold": "z", "deadline": _future_iso()},
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 422


def test_create_criterion_past_deadline_rejected(mongo_db):
    idea_id = _promote()
    res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "Ship a working demo",
            "metric": "demo shipped",
            "threshold": "yes/no",
            "deadline": _future_iso(days=-1),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 422


def test_create_criterion_not_owned_404(mongo_db):
    idea_id = _promote(session_id="sess1")
    res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "Ship a working demo", "metric": "demo shipped",
            "threshold": "yes/no", "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "someone-else"},
    )
    assert res.status_code == 404


def test_list_criteria(mongo_db):
    idea_id = _promote()
    client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "Ship a working demo", "metric": "demo shipped",
            "threshold": "yes/no", "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    res = client.get(f"/v1/ideas/{idea_id}/criteria", headers={SESSION_HEADER: "sess1"})
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_resolve_criterion_triggers_rescore(mongo_db):
    idea_id = _promote()
    create_res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "If fewer than 10/30 vets reply positively, pivot.",
            "metric": "positive replies", "threshold": ">= 10 of 30", "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    criterion_id = create_res.json()["criterion_id"]

    res = client.post(
        f"/v1/criteria/{criterion_id}/resolve",
        json={"outcome": "met", "note": "14 of 30 replied positively."},
        headers={SESSION_HEADER: "sess1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "met"

    history = asyncio.run(log_service.get_snapshot_history(idea_id))
    assert len(history) == 2
    assert history[-1].trigger == "evidence"


def test_resolve_criterion_not_owned_404(mongo_db):
    idea_id = _promote(session_id="sess1")
    create_res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "Ship a working demo", "metric": "demo shipped",
            "threshold": "yes/no", "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    criterion_id = create_res.json()["criterion_id"]

    res = client.post(
        f"/v1/criteria/{criterion_id}/resolve",
        json={"outcome": "met", "note": "done"},
        headers={SESSION_HEADER: "someone-else"},
    )
    assert res.status_code == 404


def test_resolve_already_resolved_criterion_conflict(mongo_db):
    idea_id = _promote()
    create_res = client.post(
        f"/v1/ideas/{idea_id}/criteria",
        json={
            "statement": "Ship a working demo", "metric": "demo shipped",
            "threshold": "yes/no", "deadline": _future_iso(),
        },
        headers={SESSION_HEADER: "sess1"},
    )
    criterion_id = create_res.json()["criterion_id"]

    client.post(
        f"/v1/criteria/{criterion_id}/resolve",
        json={"outcome": "met", "note": "done"},
        headers={SESSION_HEADER: "sess1"},
    )
    second = client.post(
        f"/v1/criteria/{criterion_id}/resolve",
        json={"outcome": "failed", "note": "done again"},
        headers={SESSION_HEADER: "sess1"},
    )
    assert second.status_code == 409
