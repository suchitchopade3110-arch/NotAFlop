from models.documents import AgentResultRecord, ReportDocument
from repositories import report_repository
from services import log_service, rescore_service
from services.gate import WEIGHTS_VERSION


async def _seed_idea(session_id="sess1", public_id="rep0000001"):
    report = ReportDocument(
        public_id=public_id,
        session_id=session_id,
        idea_hash=f"hash-{public_id}",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"),
            "timing": AgentResultRecord(agent="timing", passed=True, score=6, evidence="e", feedback="f", model="m"),
        },
        weights_version=WEIGHTS_VERSION,
        raw_score=70,
        verdict="go",
    )
    await report_repository.create_report(report)
    return await log_service.promote_report_to_idea(
        report, session_id=session_id, account_id=None, share_token=f"tok_{public_id}"
    )


async def test_rescore_skips_when_already_current(mongo_db):
    idea = await _seed_idea()  # already at current WEIGHTS_VERSION
    status, snapshot_id = await rescore_service.rescore_idea(idea)
    assert status == "skipped_no_change"
    assert snapshot_id is None

    history = await log_service.get_snapshot_history(idea.idea_id)
    assert len(history) == 1  # nothing written


async def test_rescore_writes_new_snapshot_when_version_differs(mongo_db, monkeypatch):
    import services.log_service as ls

    idea = await _seed_idea()
    # Simulate a weights bump AFTER this idea's last snapshot was written.
    monkeypatch.setattr(ls, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    import services.rescore_service as rs
    monkeypatch.setattr(rs, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)

    status, snapshot_id = await rescore_service.rescore_idea(idea)
    assert status == "rescored"
    assert snapshot_id is not None

    history = await log_service.get_snapshot_history(idea.idea_id)
    assert len(history) == 2
    new_snapshot = history[-1]
    assert new_snapshot.weights_version == WEIGHTS_VERSION + 1
    assert new_snapshot.trigger == "manual"
    assert new_snapshot.version_crossing is True
    # Dimension scores are untouched — only the aggregate weighting moved.
    assert new_snapshot.agent_scores == history[0].agent_scores
    assert new_snapshot.deltas["dimensions"] == {}


async def test_rescore_never_mutates_historical_snapshot(mongo_db, monkeypatch):
    import services.log_service as ls
    import services.rescore_service as rs

    idea = await _seed_idea()
    original = await log_service.get_latest_snapshot(idea.idea_id)

    monkeypatch.setattr(ls, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    monkeypatch.setattr(rs, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    await rescore_service.rescore_idea(idea)

    from repositories import snapshot_repository
    unchanged = await snapshot_repository.get_by_id(original.snapshot_id)
    assert unchanged.weights_version == original.weights_version
    assert unchanged.raw_score == original.raw_score


async def test_rescore_all_active_sweeps_every_idea(mongo_db, monkeypatch):
    import services.log_service as ls
    import services.rescore_service as rs

    idea1 = await _seed_idea(session_id="sess1", public_id="rep0000001")
    idea2 = await _seed_idea(session_id="sess2", public_id="rep0000002")

    monkeypatch.setattr(ls, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)
    monkeypatch.setattr(rs, "WEIGHTS_VERSION", WEIGHTS_VERSION + 1)

    results = await rescore_service.rescore_all_active()
    statuses = {idea_id: status for idea_id, status, _ in results}
    assert statuses[idea1.idea_id] == "rescored"
    assert statuses[idea2.idea_id] == "rescored"


async def test_rescore_idea_with_no_snapshot_fails(mongo_db):
    from models.documents import IdeaDocument
    from repositories import idea_repository

    orphan = IdeaDocument(
        idea_id="idea_orphan_rescore", session_id="sess1", idea_hash="h", raw_text="x",
        normalized_text="x", share_token="tok_orphan_rescore",
    )
    await idea_repository.create_idea(orphan)  # bypasses log_service, no snapshot

    status, snapshot_id = await rescore_service.rescore_idea(orphan)
    assert status == "failed"
    assert snapshot_id is None
