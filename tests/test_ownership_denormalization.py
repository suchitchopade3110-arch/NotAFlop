"""
Hard constraint #3 — "Every persisted document carries session_id and
nullable account_id from the first migration. No exceptions."

The five-collection schema table (A2) only lists session_id/account_id
as key fields on `ideas`, but the constraint is unqualified — so
snapshots/criteria/evidence carry a denormalized copy from their owning
idea at write time too, exactly like ReportDocument.account_id already
behaves in v1: written once, never retroactively backfilled if the
owning idea is claimed later.
"""
from datetime import datetime, timedelta, timezone

import pytest

from agents.specialist_agents import ALL_AGENTS
from models.documents import AgentResultRecord, ReportDocument
from models.schemas import CriterionRequest, EvidenceRequest
from orchestrator.state import AgentOutput
from repositories import report_repository
from services import criteria_service, evidence_service, log_service, snapshot_worker


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=7, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


async def _seed_idea(session_id="sess-owner"):
    report = ReportDocument(
        public_id="rep_owner1",
        session_id=session_id,
        idea_hash="hash_owner",
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
        report, session_id=session_id, account_id=None, share_token="tok_owner1"
    )


async def test_initial_snapshot_carries_session_id_and_null_account_id(mongo_db):
    idea = await _seed_idea()
    snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    assert snapshot.session_id == "sess-owner"
    assert snapshot.account_id is None


async def test_rescored_snapshot_carries_ownership_forward(mongo_db):
    idea = await _seed_idea()
    snapshot = await snapshot_worker.run_manual_snapshot(idea)
    assert snapshot.session_id == "sess-owner"
    assert snapshot.account_id is None


async def test_criterion_carries_ownership(mongo_db):
    idea = await _seed_idea()
    criterion = await criteria_service.create_criterion(
        idea,
        CriterionRequest(
            statement="Ship a working demo", metric="demo shipped", threshold="yes/no",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
        ),
    )
    assert criterion.session_id == "sess-owner"
    assert criterion.account_id is None


async def test_evidence_carries_ownership(mongo_db):
    idea = await _seed_idea()
    result = await evidence_service.submit_evidence(idea, EvidenceRequest(type="waitlist", payload={"count": 10}))
    evidence, _snapshot = result
    assert evidence.session_id == "sess-owner"
    assert evidence.account_id is None


async def test_documents_written_after_claim_carry_the_account_id(mongo_db):
    """Ownership on a document is fixed at write time — a claim doesn't
    retroactively touch anything written before it (matching how
    ReportDocument.account_id already behaves in v1), but anything
    written AFTER the claim picks it up, because it reads it fresh off
    the (now-claimed) idea passed in."""
    idea = await _seed_idea(session_id="sess-to-claim")
    pre_claim_snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    assert pre_claim_snapshot.account_id is None

    await log_service.claim_ideas("sess-to-claim", "acct_claimed_1")
    claimed_idea = await log_service.get_idea(idea.idea_id)
    assert claimed_idea.account_id == "acct_claimed_1"

    # Pre-claim snapshot is untouched.
    still_none = await log_service.get_latest_snapshot(idea.idea_id)
    assert still_none.account_id is None

    # A post-claim write carries the account.
    post_claim_snapshot = await snapshot_worker.run_manual_snapshot(claimed_idea)
    assert post_claim_snapshot.account_id == "acct_claimed_1"

    criterion = await criteria_service.create_criterion(
        claimed_idea,
        CriterionRequest(
            statement="Ship a working demo", metric="demo shipped", threshold="yes/no",
            deadline=datetime.now(timezone.utc) + timedelta(days=30),
        ),
    )
    assert criterion.account_id == "acct_claimed_1"
