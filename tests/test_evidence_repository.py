from models.documents import EvidenceDocument
from repositories import evidence_repository as repo


def _make_evidence(evidence_id="ev_0000000001", idea_id="idea_1") -> EvidenceDocument:
    return EvidenceDocument(
        evidence_id=evidence_id,
        idea_id=idea_id,
        type="waitlist",
        payload={"count": 120, "source": "landing page"},
    )


async def test_create_and_get_by_id(mongo_db):
    doc = _make_evidence()
    assert await repo.create_evidence(doc) is True

    fetched = await repo.get_by_id(doc.evidence_id)
    assert fetched is not None
    assert fetched.payload["count"] == 120
    assert fetched.triggered_snapshot_id is None


async def test_list_by_idea(mongo_db):
    await repo.create_evidence(_make_evidence(evidence_id="ev_0000000001"))
    await repo.create_evidence(_make_evidence(evidence_id="ev_0000000002"))
    await repo.create_evidence(_make_evidence(evidence_id="ev_0000000003", idea_id="idea_2"))

    listed = await repo.list_by_idea("idea_1")
    assert {e.evidence_id for e in listed} == {"ev_0000000001", "ev_0000000002"}


async def test_set_triggered_snapshot(mongo_db):
    doc = _make_evidence()
    await repo.create_evidence(doc)
    assert await repo.set_triggered_snapshot(doc.evidence_id, "snap_1") is True

    fetched = await repo.get_by_id(doc.evidence_id)
    assert fetched.triggered_snapshot_id == "snap_1"


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    doc = _make_evidence()
    assert await repo.create_evidence(doc) is False
    assert await repo.get_by_id(doc.evidence_id) is None
    assert await repo.list_by_idea("idea_1") == []
    assert await repo.set_triggered_snapshot(doc.evidence_id, "snap_1") is False
