import pytest

from agents.specialist_agents import ALL_AGENTS
from models.documents import AgentResultRecord, IdeaDocument, ReportDocument
from orchestrator.state import AgentOutput
from services import log_service, snapshot_worker


def _patch_agents(monkeypatch, scores: dict[str, int], default=5):
    """Deterministic fake agent.run() — score comes from `scores` by
    name, or `default` for anything not listed."""
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            score = scores.get(_name, default)
            return AgentOutput(agent=_name, passed=score >= 6, score=score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    async def _fake_gather_signals(keyword):
        return {
            "keyword": keyword,
            "signals": {"reddit": {"status": "ok", "post_count": 10}},
        }

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)


async def _seed_idea(mongo_db) -> IdeaDocument:
    report = ReportDocument(
        public_id="rep0000001",
        session_id="sess1",
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        signals={"reddit": {"status": "ok", "post_count": 5}},
        agent_results={
            name: AgentResultRecord(agent=name, passed=True, score=6, evidence="e", feedback="f", model="m")
            for name in ["problem", "solution", "timing", "tam", "moat", "team", "unit_economics", "gtm", "ask", "risk", "yc_signal", "lovers_test"]
        },
        weights_version=2,
        raw_score=60,
        verdict="pivot",
    )
    await __import__("repositories.report_repository", fromlist=["create_report"]).create_report(report)
    return await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_worker"
    )


async def test_scheduled_snapshot_moves_only_market_dimensions(mongo_db, monkeypatch):
    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 9, "tam": 6, "moat": 6})  # tam/moat unchanged from 6

    snapshot = await snapshot_worker.run_scheduled_snapshot(idea)
    assert snapshot is not None
    assert snapshot.trigger == "scheduled"
    assert set(snapshot.deltas["dimensions"].keys()) == {"timing", "tam", "moat"}
    assert snapshot.deltas["dimensions"]["timing"] == 3
    # Every other dimension carried forward unchanged.
    assert snapshot.agent_scores["problem"] == 6
    assert snapshot.agent_scores["team"] == 6


async def test_manual_snapshot_same_dimension_set(mongo_db, monkeypatch):
    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 8})

    snapshot = await snapshot_worker.run_manual_snapshot(idea)
    assert snapshot.trigger == "manual"
    assert set(snapshot.deltas["dimensions"].keys()) == {"timing", "tam", "moat"}


async def test_evidence_snapshot_moves_only_evidence_gated_dimensions(mongo_db, monkeypatch):
    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"problem": 9, "solution": 6})

    snapshot = await snapshot_worker.run_evidence_snapshot(idea, "12 of 30 cold-emailed vets replied positively.")
    assert snapshot.trigger == "evidence"
    assert set(snapshot.deltas["dimensions"].keys()) == {
        "problem", "solution", "team", "unit_economics", "gtm", "ask",
    }
    assert snapshot.deltas["dimensions"]["problem"] == 3
    # Market-sensitive dims untouched by evidence.
    assert snapshot.agent_scores["timing"] == 6
    assert "timing" not in snapshot.deltas["dimensions"]


async def test_evidence_snapshot_does_not_refetch_data_layer(mongo_db, monkeypatch):
    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {})

    calls = []

    async def _tracked(keyword):
        calls.append(keyword)
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _tracked)

    await snapshot_worker.run_evidence_snapshot(idea, "some evidence")
    assert calls == []  # never called — evidence-gated re-runs reuse prior signals


async def test_snapshot_cost_recorded(mongo_db, monkeypatch):
    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 7})

    from services import cost_tracking

    monkeypatch.setattr(cost_tracking, "get_total_cost_usd", lambda: 0.03)
    snapshot = await snapshot_worker.run_scheduled_snapshot(idea)
    assert snapshot.cost == 0.03


async def test_is_due_true_for_idea_with_no_snapshot_gap(mongo_db):
    idea = await _seed_idea(mongo_db)
    assert await snapshot_worker.is_due_for_scheduled_snapshot(idea) is False


async def test_is_due_true_once_interval_elapsed(mongo_db):
    import datetime as dt

    from core.config import SNAPSHOT_SCHEDULE_INTERVAL_DAYS

    idea = await _seed_idea(mongo_db)
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=SNAPSHOT_SCHEDULE_INTERVAL_DAYS + 1)
    assert await snapshot_worker.is_due_for_scheduled_snapshot(idea, now=future) is True


async def test_locked_idea_skips_concurrent_run(mongo_db, monkeypatch):
    from repositories import idea_repository

    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 9})

    assert await idea_repository.try_acquire_scheduler_lock(idea.idea_id, 60) is True
    result = await snapshot_worker.run_manual_snapshot(idea)
    assert result is None  # lock already held — skipped, no snapshot written

    history = await log_service.get_snapshot_history(idea.idea_id)
    assert len(history) == 1  # only the initial snapshot


async def test_manual_snapshot_releases_lock_after_completion(mongo_db, monkeypatch):
    from repositories import idea_repository

    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 9})

    await snapshot_worker.run_manual_snapshot(idea)
    # Lock released — a second run is allowed immediately after.
    assert await idea_repository.try_acquire_scheduler_lock(idea.idea_id, 60) is True


async def test_sweep_due_ideas_only_runs_due_ones(mongo_db, monkeypatch):
    import datetime as dt

    from core.config import SNAPSHOT_SCHEDULE_INTERVAL_DAYS
    from repositories import snapshot_repository

    idea = await _seed_idea(mongo_db)
    _patch_agents(monkeypatch, {"timing": 9})

    # Fresh idea — not due yet.
    written = await snapshot_worker.sweep_due_ideas()
    assert written == []

    # Backdate its only snapshot so it's now overdue.
    latest = await snapshot_repository.get_latest_for_idea(idea.idea_id)
    coll = snapshot_repository._collection()
    overdue = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=SNAPSHOT_SCHEDULE_INTERVAL_DAYS + 1)
    await coll.update_one({"snapshot_id": latest.snapshot_id}, {"$set": {"created_at": overdue}})

    written = await snapshot_worker.sweep_due_ideas()
    assert len(written) == 1
    assert written[0].idea_id == idea.idea_id
    assert written[0].trigger == "scheduled"
