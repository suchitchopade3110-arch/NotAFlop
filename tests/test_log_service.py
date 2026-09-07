from models.documents import AgentResultRecord, ReportDocument
from services import log_service


def _make_report(public_id="rep0000001", session_id="sess1") -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id=session_id,
        ip="1.2.3.4",
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        signals={"reddit": {"post_count": 10}, "hacker_news": {"post_count": 2}},
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"),
            "timing": AgentResultRecord(agent="timing", passed=True, score=6, evidence="e", feedback="f", model="m"),
            "tam": AgentResultRecord(agent="tam", passed=True, score=7, evidence="e", feedback="f", model="m"),
        },
        signal_quality=0.8,
        conflicts=[{"dimension": "tam", "sources": ["reddit", "hacker_news"], "directions": ["up", "down"], "description": "d"}],
        report_cost_usd=0.05,
        weights_version=2,
        raw_score=75,
        adjusted_score=75,
        verdict="go",
    )


async def test_promote_report_to_idea_mirrors_report_score(mongo_db):
    report = _make_report()
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_abc"
    )
    assert idea is not None
    assert idea.idea_hash == "hash1"
    assert idea.raw_text == "Uber for dog walking"
    assert idea.source_report_id == "rep0000001"
    assert idea.current_snapshot_id is not None

    snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    assert snapshot.raw_score == 75
    assert snapshot.verdict == "go"
    assert snapshot.weights_version == 2
    assert snapshot.trigger == "initial"
    assert snapshot.deltas == {}
    assert snapshot.version_crossing is False
    assert snapshot.agent_scores == {"problem": 8, "timing": 6, "tam": 7}
    assert snapshot.signal_quality == 0.8
    assert snapshot.cost == 0.0


async def test_promote_rolls_back_idea_if_snapshot_write_fails(mongo_db, monkeypatch):
    from repositories import snapshot_repository

    async def _fail(_doc):
        return False

    monkeypatch.setattr(snapshot_repository, "create_snapshot", _fail)

    report = _make_report()
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_fail"
    )
    assert idea is None

    from repositories import idea_repository
    owned = await idea_repository.list_owned("sess1", None)
    assert owned == []


async def test_record_snapshot_carries_forward_untouched_dimensions(mongo_db):
    report = _make_report()
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_carry"
    )

    snapshot = await log_service.record_snapshot(
        idea, trigger="scheduled", updated_scores={"timing": 9, "tam": 7},  # tam unchanged, timing moves
        sources=["reddit"], signal_quality=0.9, conflicts=[], cost=0.05,
    )
    assert snapshot is not None
    # problem was never re-run — carried forward byte-for-byte.
    assert snapshot.agent_scores["problem"] == 8
    assert snapshot.agent_scores["timing"] == 9
    assert snapshot.agent_scores["tam"] == 7
    assert snapshot.trigger == "scheduled"
    assert snapshot.deltas["dimensions"] == {"timing": 3, "tam": 0}
    assert "problem" not in snapshot.deltas["dimensions"]
    assert snapshot.cost == 0.05


async def test_record_snapshot_deltas_store_weights_version_on_both_sides(mongo_db):
    report = _make_report()  # weights_version=2
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_bothsides"
    )

    snapshot = await log_service.record_snapshot(idea, trigger="scheduled", updated_scores={"timing": 9})
    assert snapshot.deltas["previous_weights_version"] == 2
    assert snapshot.deltas["current_weights_version"] == 2
    assert snapshot.version_crossing is False


async def test_record_snapshot_dimension_deltas_survive_version_crossing(mongo_db, monkeypatch):
    """C2: per-dimension deltas stay a like-for-like diff even across a
    weights change (the rubric each dimension is scored against doesn't
    change) — only the AGGREGATE delta is what version_crossing warns a
    reader not to read as market movement."""
    import services.log_service as ls

    report = _make_report()  # weights_version=2
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_crossdim"
    )

    monkeypatch.setattr(ls, "WEIGHTS_VERSION", 3)
    snapshot = await log_service.record_snapshot(idea, trigger="scheduled", updated_scores={"timing": 9})

    assert snapshot.version_crossing is True
    assert snapshot.deltas["previous_weights_version"] == 2
    assert snapshot.deltas["current_weights_version"] == 3
    # The per-dimension delta is still the honest arithmetic diff — not
    # suppressed or zeroed out just because the versions differ.
    assert snapshot.deltas["dimensions"]["timing"] == 3


async def test_record_snapshot_version_crossing_flagged(mongo_db, monkeypatch):
    import services.log_service as ls

    report = _make_report()  # weights_version=2
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_ver"
    )

    monkeypatch.setattr(ls, "WEIGHTS_VERSION", 3)
    snapshot = await log_service.record_snapshot(idea, trigger="manual", updated_scores={"timing": 5})
    assert snapshot.weights_version == 3
    assert snapshot.version_crossing is True


async def test_record_snapshot_returns_none_without_previous(mongo_db):
    from models.documents import IdeaDocument

    orphan = IdeaDocument(
        idea_id="idea_orphan01", session_id="sess1", idea_hash="h", raw_text="x",
        normalized_text="x", share_token="tok_orphan",
    )
    result = await log_service.record_snapshot(orphan, trigger="scheduled", updated_scores={"timing": 5})
    assert result is None


async def test_delete_idea_cascade_removes_everything(mongo_db):
    from models.documents import CriterionDocument, EvidenceDocument
    from repositories import criteria_repository, evidence_repository, idea_repository, snapshot_repository
    from datetime import datetime, timedelta, timezone

    report = _make_report()
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_del"
    )
    await criteria_repository.create_criterion(
        CriterionDocument(
            criterion_id="crit_del1", idea_id=idea.idea_id, statement="s", metric="m",
            threshold="t", deadline=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    await evidence_repository.create_evidence(
        EvidenceDocument(evidence_id="ev_del1", idea_id=idea.idea_id, type="waitlist", payload={})
    )

    assert await log_service.delete_idea_cascade(idea.idea_id) is True
    assert await idea_repository.get_by_id(idea.idea_id) is None
    assert await snapshot_repository.list_by_idea(idea.idea_id) == []
    assert await criteria_repository.list_by_idea(idea.idea_id) == []
    assert await evidence_repository.list_by_idea(idea.idea_id) == []


async def test_claim_ideas_transfers_ownership(mongo_db):
    report = _make_report()
    idea = await log_service.promote_report_to_idea(
        report, session_id="sess1", account_id=None, share_token="tok_claim"
    )
    moved = await log_service.claim_ideas("sess1", "acct_1")
    assert moved == 1

    fetched = await log_service.get_idea(idea.idea_id)
    assert fetched.account_id == "acct_1"
    assert log_service.owns_idea(fetched, "sess1", "acct_1") is True
