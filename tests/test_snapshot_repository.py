from models.documents import SnapshotDocument
from repositories import snapshot_repository as repo


def _make_snapshot(snapshot_id="snap_0000000001", idea_id="idea_1", raw_score=70, trigger="initial") -> SnapshotDocument:
    return SnapshotDocument(
        snapshot_id=snapshot_id,
        idea_id=idea_id,
        session_id="sess1",
        agent_scores={"problem": 8, "solution": 7},
        raw_score=raw_score,
        verdict="go",
        weights_version=2,
        trigger=trigger,
    )


async def test_create_and_get_by_id(mongo_db):
    doc = _make_snapshot()
    assert await repo.create_snapshot(doc) is True

    fetched = await repo.get_by_id(doc.snapshot_id)
    assert fetched is not None
    assert fetched.raw_score == 70
    assert fetched.agent_scores["problem"] == 8


async def test_get_latest_for_idea(mongo_db):
    import asyncio

    first = _make_snapshot(snapshot_id="snap_0000000001", raw_score=60)
    await repo.create_snapshot(first)
    await asyncio.sleep(0.01)
    second = _make_snapshot(snapshot_id="snap_0000000002", raw_score=65, trigger="scheduled")
    await repo.create_snapshot(second)

    latest = await repo.get_latest_for_idea("idea_1")
    assert latest.snapshot_id == "snap_0000000002"


async def test_list_by_idea_oldest_first(mongo_db):
    import asyncio

    first = _make_snapshot(snapshot_id="snap_0000000001", raw_score=60)
    await repo.create_snapshot(first)
    await asyncio.sleep(0.01)
    second = _make_snapshot(snapshot_id="snap_0000000002", raw_score=65, trigger="scheduled")
    await repo.create_snapshot(second)

    history = await repo.list_by_idea("idea_1")
    assert [s.snapshot_id for s in history] == ["snap_0000000001", "snap_0000000002"]


async def test_delete_by_idea(mongo_db):
    await repo.create_snapshot(_make_snapshot())
    deleted = await repo.delete_by_idea("idea_1")
    assert deleted == 1
    assert await repo.list_by_idea("idea_1") == []


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    doc = _make_snapshot()
    assert await repo.create_snapshot(doc) is False
    assert await repo.get_by_id(doc.snapshot_id) is None
    assert await repo.get_latest_for_idea("idea_1") is None
    assert await repo.list_by_idea("idea_1") == []
    assert await repo.delete_by_idea("idea_1") == 0
