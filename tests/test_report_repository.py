import logging

from models.documents import AgentResultRecord, ReportDocument, VerifierOutput
from repositories import report_repository as repo


def _make_report(public_id="abc1234567", idea_hash="hash1", session_id="sess1") -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id=session_id,
        ip="1.2.3.4",
        idea_hash=idea_hash,
        transcript="Uber for dog walking",
        keyword="dog walking",
        signals={"reddit": {"post_count": 10}},
        agent_results={
            "problem": AgentResultRecord(
                agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"
            )
        },
        weights_version=1,
        raw_score=80,
        verdict="go",
    )


async def test_create_and_get_report(mongo_db):
    doc = _make_report()
    ok = await repo.create_report(doc)
    assert ok is True

    fetched = await repo.get_by_public_id(doc.public_id)
    assert fetched is not None
    assert fetched.public_id == doc.public_id
    assert fetched.raw_score == 80
    assert fetched.agent_results["problem"].score == 8


async def test_get_by_public_id_missing_returns_none(mongo_db):
    assert await repo.get_by_public_id("does-not-exist") is None


async def test_create_report_noop_when_mongo_unavailable(mongo_unavailable):
    doc = _make_report()
    ok = await repo.create_report(doc)
    assert ok is False


async def test_list_by_session_sorted_newest_first(mongo_db):
    doc1 = _make_report(public_id="pid0000001", idea_hash="h1", session_id="s1")
    doc2 = _make_report(public_id="pid0000002", idea_hash="h2", session_id="s1")
    await repo.create_report(doc1)
    await repo.create_report(doc2)

    other_session = _make_report(public_id="pid0000003", idea_hash="h3", session_id="s2")
    await repo.create_report(other_session)

    results = await repo.list_by_session("s1")
    assert {r.public_id for r in results} == {"pid0000001", "pid0000002"}


async def test_idea_hash_hit_rate_is_logged(mongo_db, caplog):
    caplog.set_level(logging.INFO, logger="notaflop.repositories.report")

    doc1 = _make_report(public_id="pidfirst001", idea_hash="repeat-hash")
    await repo.create_report(doc1)
    assert "is_repeat=False" in caplog.text

    caplog.clear()
    doc2 = _make_report(public_id="pidsecond02", idea_hash="repeat-hash")
    await repo.create_report(doc2)
    assert "is_repeat=True" in caplog.text
    assert "prior_count=1" in caplog.text


async def test_patch_verifier_updates_existing_report(mongo_db):
    doc = _make_report()
    await repo.create_report(doc)

    verifier = VerifierOutput(
        confidence_score=3,
        passed=False,
        conflicts=["problem and solution disagree on the buyer"],
        evidence="e",
        feedback="f",
        model="m",
    )
    ok = await repo.patch_verifier(doc.public_id, verifier, adjusted_score=60, verdict_would_flip=True)
    assert ok is True

    fetched = await repo.get_by_public_id(doc.public_id)
    assert fetched.verifier is not None
    assert fetched.verifier.confidence_score == 3
    assert fetched.adjusted_score == 60
    assert fetched.verdict_would_flip is True


async def test_patch_verifier_noop_when_mongo_unavailable(mongo_unavailable):
    verifier = VerifierOutput(confidence_score=5, passed=True, evidence="e", feedback="f", model="m")
    ok = await repo.patch_verifier("whatever", verifier, adjusted_score=50, verdict_would_flip=False)
    assert ok is False
