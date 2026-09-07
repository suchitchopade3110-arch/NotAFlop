"""
C5 — the core rule, proven explicitly.

"The score moves when the founder produces evidence. Not when time
passes. Not when they rewrite the pitch. Evidence, or the number
stands."

Each test below isolates ONE way the product could accidentally violate
that rule and shows it doesn't. This file is deliberately self-contained
(its own fixtures, its own idea seed) rather than reusing helpers spread
across the other Phase 2 test files — it's meant to read as the one
place that proves the product's central promise, not as incidental
coverage of some other task's code path.
"""
import asyncio
import datetime as dt

import pytest

from agents.specialist_agents import ALL_AGENTS
from models.documents import AgentResultRecord, ReportDocument
from models.schemas import CriterionRequest, EvidenceRequest
from orchestrator.state import AgentOutput
from repositories import idea_repository, report_repository, snapshot_repository
from services import criteria_service, evidence_service, log_service, snapshot_worker

ALL_DIMENSIONS = [
    "problem", "solution", "timing", "tam", "moat", "team",
    "unit_economics", "gtm", "ask", "risk", "yc_signal", "lovers_test",
]


def _patch_agents(monkeypatch, overrides: dict[str, int], default: int = 6):
    """Every dimension agent returns `default` unless overridden — so a
    test can prove exactly which dimensions moved by only overriding the
    ones it expects to change."""
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            score = overrides.get(_name, default)
            return AgentOutput(agent=_name, passed=score >= 6, score=score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    """No live network in this suite — the scheduled/manual re-run's
    'always refresh the data layer' step is faked out, not skipped, so
    the rule is proven against the real code path."""
    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {"reddit": {"status": "ok", "post_count": 5}}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)


async def _seed_idea(session_id="sess-core-rule"):
    """Every dimension starts at 6 — a flat baseline makes any single
    dimension moving unmistakable."""
    report = ReportDocument(
        public_id="rep_core_rule1",
        session_id=session_id,
        idea_hash="hash_core_rule",
        transcript="A marketplace connecting freelance vets with pet owners for on-demand house calls.",
        keyword="pet house calls",
        agent_results={
            name: AgentResultRecord(agent=name, passed=True, score=6, evidence="e", feedback="f", model="m")
            for name in ALL_DIMENSIONS
        },
        weights_version=2,
        raw_score=60,
        verdict="pivot",
    )
    await report_repository.create_report(report)
    return await log_service.promote_report_to_idea(
        report, session_id=session_id, account_id=None, share_token="tok_core_rule"
    )


async def _snapshot_count(idea_id: str) -> int:
    return len(await log_service.get_snapshot_history(idea_id))


# ── 1. Time passing alone produces no score change ────────────────────

async def test_time_passing_alone_produces_no_score_change(mongo_db):
    idea = await _seed_idea()
    initial = await log_service.get_latest_snapshot(idea.idea_id)

    # Simulate a long stretch of real time passing — the idea is now
    # objectively "due" for a scheduled re-run — WITHOUT anything ever
    # invoking the scheduler or a manual re-run. Merely reading the idea
    # back, repeatedly, across that gap, must never write a snapshot.
    far_future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365)
    assert await snapshot_worker.is_due_for_scheduled_snapshot(idea, now=far_future) is True

    for _ in range(5):
        await log_service.get_idea(idea.idea_id)
        await log_service.get_latest_snapshot(idea.idea_id)

    assert await _snapshot_count(idea.idea_id) == 1
    unchanged = await log_service.get_latest_snapshot(idea.idea_id)
    assert unchanged.snapshot_id == initial.snapshot_id
    assert unchanged.raw_score == initial.raw_score
    assert unchanged.agent_scores == initial.agent_scores


# ── 2. Pitch text edited alone produces no score change ────────────────

async def test_pitch_text_edited_alone_produces_no_score_change(mongo_db):
    """There is no route or service function anywhere in Phase 2 that
    edits IdeaDocument.raw_text and reacts to it — editing the pitch
    simply isn't wired to anything that scores. This test edits raw_text
    directly at the repository layer (the only way it could even happen)
    and shows the score sits untouched."""
    idea = await _seed_idea()
    initial = await log_service.get_latest_snapshot(idea.idea_id)

    coll = idea_repository._collection()
    await coll.update_one(
        {"idea_id": idea.idea_id},
        {"$set": {"raw_text": "A completely different pitch: a B2B logistics SaaS for cold-chain trucking."}},
    )

    edited_idea = await log_service.get_idea(idea.idea_id)
    assert edited_idea.raw_text != idea.raw_text  # the edit really happened

    assert await _snapshot_count(idea.idea_id) == 1
    unchanged = await log_service.get_latest_snapshot(idea.idea_id)
    assert unchanged.snapshot_id == initial.snapshot_id
    assert unchanged.raw_score == initial.raw_score
    assert unchanged.agent_scores == initial.agent_scores


# ── 3. A scheduled snapshot moves only Timing / TAM / Moat ─────────────

async def test_scheduled_snapshot_moves_only_timing_tam_moat(mongo_db, monkeypatch):
    idea = await _seed_idea()
    _patch_agents(monkeypatch, {"timing": 9, "tam": 2, "moat": 6})  # moat unchanged from baseline 6

    snapshot = await snapshot_worker.run_scheduled_snapshot(idea)
    assert snapshot is not None
    assert snapshot.trigger == "scheduled"

    moved = {dim for dim, delta in snapshot.deltas["dimensions"].items() if delta != 0}
    assert moved <= {"timing", "tam", "moat"}
    assert snapshot.deltas["dimensions"]["timing"] == 3
    assert snapshot.deltas["dimensions"]["tam"] == -4

    for dim in ALL_DIMENSIONS:
        if dim in ("timing", "tam", "moat"):
            continue
        assert snapshot.agent_scores[dim] == 6, f"{dim} must be carried forward unchanged, got {snapshot.agent_scores[dim]}"
        assert dim not in snapshot.deltas["dimensions"]


# ── 4. Evidence submission moves the gated set ──────────────────────────

async def test_evidence_submission_moves_only_the_gated_set(mongo_db, monkeypatch):
    idea = await _seed_idea()
    _patch_agents(monkeypatch, {"problem": 9, "gtm": 8, "timing": 10, "tam": 10, "moat": 10})

    result = await evidence_service.submit_evidence(
        idea, EvidenceRequest(type="waitlist", payload={"count": 340})
    )
    assert result is not None
    evidence, snapshot = result
    assert snapshot.trigger == "evidence"

    gated = {"problem", "solution", "team", "unit_economics", "gtm", "ask"}
    moved = {dim for dim, delta in snapshot.deltas["dimensions"].items() if delta != 0}
    assert moved <= gated
    assert snapshot.deltas["dimensions"]["problem"] == 3
    assert snapshot.deltas["dimensions"]["gtm"] == 2

    # Timing/TAM/Moat were pushed to 10 in the fake agent, but evidence
    # never re-runs them — they must still read the original baseline.
    for dim in ("timing", "tam", "moat"):
        assert snapshot.agent_scores[dim] == 6
        assert dim not in snapshot.deltas["dimensions"]


# ── 5. A resolved kill-criterion triggers a re-score ────────────────────

async def test_resolved_kill_criterion_triggers_a_rescore(mongo_db, monkeypatch):
    idea = await _seed_idea()
    _patch_agents(monkeypatch, {"solution": 9})

    criterion = await criteria_service.create_criterion(
        idea,
        CriterionRequest(
            statement="If fewer than 10/30 cold-emailed vets reply positively, pivot.",
            metric="positive vet replies",
            threshold=">= 10 of 30",
            deadline=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30),
        ),
    )
    assert await _snapshot_count(idea.idea_id) == 1  # committing the criterion alone changes nothing

    result = await criteria_service.resolve_criterion(
        criterion, idea, "met", "14 of 30 vets replied positively."
    )
    assert result is not None
    resolved, evidence = result

    assert resolved.status == "met"
    assert evidence.type == "criterion_resolution"
    assert evidence.triggered_snapshot_id is not None

    assert await _snapshot_count(idea.idea_id) == 2
    latest = await log_service.get_latest_snapshot(idea.idea_id)
    assert latest.trigger == "evidence"
    assert latest.deltas["dimensions"]["solution"] == 3


# ── Cross-check: a failed/skipped re-run never writes a partial snapshot ─

async def test_locked_or_failed_rerun_never_corrupts_current_snapshot(mongo_db, monkeypatch):
    idea = await _seed_idea()
    initial_snapshot_id = idea.current_snapshot_id

    _patch_agents(monkeypatch, {"timing": 9})
    assert await idea_repository.try_acquire_scheduler_lock(idea.idea_id, 3600) is True

    # Concurrent run finds the lock held — writes nothing, current
    # pointer stays exactly where it was.
    result = await snapshot_worker.run_manual_snapshot(idea)
    assert result is None
    assert await _snapshot_count(idea.idea_id) == 1

    persisted = await idea_repository.get_by_id(idea.idea_id)
    assert persisted.current_snapshot_id == initial_snapshot_id
