from datetime import datetime, timedelta, timezone

import pytest

from agents.specialist_agents import ALL_AGENTS
from models.documents import AgentResultRecord, ReportDocument
from models.schemas import CriterionRequest
from orchestrator.state import AgentOutput
from repositories import criteria_repository, evidence_repository, report_repository
from services import criteria_service, log_service


def _patch_agents(monkeypatch, scores: dict[str, int], default=6):
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            score = scores.get(_name, default)
            return AgentOutput(agent=_name, passed=score >= 6, score=score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    from services import snapshot_worker

    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)


async def _seed_idea(session_id="sess1"):
    report = ReportDocument(
        public_id="rep0000001",
        session_id=session_id,
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            name: AgentResultRecord(agent=name, passed=True, score=6, evidence="e", feedback="f", model="m")
            for name in ["problem", "solution", "timing", "tam", "moat", "team", "unit_economics", "gtm", "ask", "risk", "yc_signal", "lovers_test"]
        },
        weights_version=2,
        raw_score=60,
        verdict="pivot",
    )
    await report_repository.create_report(report)
    return await log_service.promote_report_to_idea(
        report, session_id=session_id, account_id=None, share_token="tok_crit"
    )


def _future_deadline(days=30):
    return datetime.now(timezone.utc) + timedelta(days=days)


async def test_create_criterion(mongo_db):
    idea = await _seed_idea()
    body = CriterionRequest(
        statement="If fewer than 10/30 cold-emailed vets reply positively, pivot.",
        metric="positive vet replies",
        threshold=">= 10 of 30",
        deadline=_future_deadline(),
    )
    criterion = await criteria_service.create_criterion(idea, body)
    assert criterion is not None
    assert criterion.status == "pending"


async def test_list_criteria(mongo_db):
    idea = await _seed_idea()
    body = CriterionRequest(statement="Ship a working demo", metric="demo shipped", threshold="yes/no", deadline=_future_deadline())
    await criteria_service.create_criterion(idea, body)
    listed = await criteria_service.list_criteria(idea.idea_id)
    assert len(listed) == 1


async def test_resolve_criterion_writes_evidence_and_rescores(mongo_db, monkeypatch):
    idea = await _seed_idea()
    _patch_agents(monkeypatch, {"problem": 9})

    body = CriterionRequest(
        statement="If fewer than 10/30 vets reply positively, pivot.",
        metric="positive replies", threshold=">= 10 of 30", deadline=_future_deadline(),
    )
    criterion = await criteria_service.create_criterion(idea, body)

    result = await criteria_service.resolve_criterion(criterion, idea, "met", "14 of 30 replied positively.")
    assert result is not None
    resolved, evidence = result

    assert resolved.status == "met"
    assert resolved.resolution_note == "14 of 30 replied positively."
    assert resolved.resolved_at is not None

    assert evidence.type == "criterion_resolution"
    assert evidence.payload["outcome"] == "met"
    assert evidence.triggered_snapshot_id is not None

    history = await log_service.get_snapshot_history(idea.idea_id)
    assert len(history) == 2
    assert history[-1].trigger == "evidence"
    assert history[-1].agent_scores["problem"] == 9
    # Market-sensitive dims untouched by a criterion resolution.
    assert "timing" not in history[-1].deltas["dimensions"]


async def test_sweep_lapsed_criteria_transitions_overdue(mongo_db):
    idea = await _seed_idea()
    past = CriterionRequest(statement="Ship a working demo", metric="demo shipped", threshold="yes/no", deadline=_future_deadline(days=1))
    criterion = await criteria_service.create_criterion(idea, past)

    # Backdate the deadline directly (CriterionRequest itself rejects a
    # past deadline at the API boundary).
    coll = criteria_repository._collection()
    overdue = datetime.now(timezone.utc) - timedelta(days=1)
    await coll.update_one({"criterion_id": criterion.criterion_id}, {"$set": {"deadline": overdue}})

    lapsed_count = await criteria_service.sweep_lapsed_criteria()
    assert lapsed_count == 1

    fetched = await criteria_repository.get_by_id(criterion.criterion_id)
    assert fetched.status == "lapsed"


async def test_sweep_ignores_future_deadlines(mongo_db):
    idea = await _seed_idea()
    future = CriterionRequest(statement="Ship a working demo", metric="demo shipped", threshold="yes/no", deadline=_future_deadline())
    await criteria_service.create_criterion(idea, future)

    assert await criteria_service.sweep_lapsed_criteria() == 0


async def test_sweep_deadline_reminders_sends_only_to_claimed_ideas(mongo_db, monkeypatch):
    from models.documents import AccountDocument
    from repositories import account_repository

    from services.notifications import service as notifications
    from services.notifications.base import NotificationProvider

    class _Recording(NotificationProvider):
        def __init__(self):
            self.sent = []

        async def send(self, *, to, subject, body, kind):
            self.sent.append(kind)
            return True

    recording = _Recording()
    monkeypatch.setattr(notifications, "_provider", recording)

    claimed_idea = await _seed_idea(session_id="sess-claimed")
    await account_repository.create_account(AccountDocument(account_id="acct_claimed", email="f@example.com"))
    from repositories import idea_repository
    coll = idea_repository._collection()
    await coll.update_one({"idea_id": claimed_idea.idea_id}, {"$set": {"account_id": "acct_claimed"}})

    unclaimed_idea = await _seed_idea(session_id="sess-anon")

    soon = _future_deadline(days=1)
    await criteria_service.create_criterion(
        claimed_idea,
        CriterionRequest(statement="Ship a working demo", metric="demo shipped", threshold="yes/no", deadline=soon),
    )
    await criteria_service.create_criterion(
        unclaimed_idea,
        CriterionRequest(statement="Ship a working demo", metric="demo shipped", threshold="yes/no", deadline=soon),
    )

    sent_count = await criteria_service.sweep_deadline_reminders()
    assert sent_count == 1
    assert recording.sent == ["criteria_deadline"]
