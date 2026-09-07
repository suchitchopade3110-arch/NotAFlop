from datetime import datetime, timedelta, timezone

from models.documents import CriterionDocument
from repositories import criteria_repository as repo


def _make_criterion(criterion_id="crit_0000000001", idea_id="idea_1", deadline=None) -> CriterionDocument:
    return CriterionDocument(
        criterion_id=criterion_id,
        idea_id=idea_id,
        session_id="sess1",
        statement="If fewer than 10 of 30 cold-emailed vets reply positively, pivot.",
        metric="positive vet replies",
        threshold=">= 10 of 30",
        deadline=deadline or (datetime.now(timezone.utc) + timedelta(days=30)),
    )


async def test_create_and_get_by_id(mongo_db):
    doc = _make_criterion()
    assert await repo.create_criterion(doc) is True

    fetched = await repo.get_by_id(doc.criterion_id)
    assert fetched is not None
    assert fetched.status == "pending"


async def test_list_by_idea(mongo_db):
    await repo.create_criterion(_make_criterion(criterion_id="crit_0000000001"))
    await repo.create_criterion(_make_criterion(criterion_id="crit_0000000002"))
    others = await repo.create_criterion(_make_criterion(criterion_id="crit_0000000003", idea_id="idea_2"))

    listed = await repo.list_by_idea("idea_1")
    assert {c.criterion_id for c in listed} == {"crit_0000000001", "crit_0000000002"}


async def test_list_lapsable_only_past_deadline_pending(mongo_db):
    past = _make_criterion(criterion_id="crit_0000000001", deadline=datetime.now(timezone.utc) - timedelta(days=1))
    future = _make_criterion(criterion_id="crit_0000000002", deadline=datetime.now(timezone.utc) + timedelta(days=1))
    await repo.create_criterion(past)
    await repo.create_criterion(future)

    lapsable = await repo.list_lapsable()
    assert {c.criterion_id for c in lapsable} == {"crit_0000000001"}


async def test_resolve_sets_status_and_note(mongo_db):
    doc = _make_criterion()
    await repo.create_criterion(doc)
    assert await repo.resolve(doc.criterion_id, "met", "12 of 30 replied positively.") is True

    fetched = await repo.get_by_id(doc.criterion_id)
    assert fetched.status == "met"
    assert fetched.resolution_note == "12 of 30 replied positively."
    assert fetched.resolved_at is not None


async def test_mark_lapsed_only_from_pending(mongo_db):
    doc = _make_criterion()
    await repo.create_criterion(doc)
    assert await repo.mark_lapsed(doc.criterion_id) is True

    fetched = await repo.get_by_id(doc.criterion_id)
    assert fetched.status == "lapsed"

    # Already resolved — marking lapsed again is a no-op.
    assert await repo.mark_lapsed(doc.criterion_id) is False


async def test_list_needing_reminder_within_window(mongo_db):
    soon = _make_criterion(criterion_id="crit_0000000001", deadline=datetime.now(timezone.utc) + timedelta(days=1))
    far = _make_criterion(criterion_id="crit_0000000002", deadline=datetime.now(timezone.utc) + timedelta(days=30))
    await repo.create_criterion(soon)
    await repo.create_criterion(far)

    due = await repo.list_needing_reminder(within_days=3)
    assert {c.criterion_id for c in due} == {"crit_0000000001"}


async def test_list_needing_reminder_excludes_already_sent(mongo_db):
    soon = _make_criterion(deadline=datetime.now(timezone.utc) + timedelta(days=1))
    await repo.create_criterion(soon)
    await repo.mark_reminder_sent(soon.criterion_id)

    assert await repo.list_needing_reminder(within_days=3) == []


async def test_mark_reminder_sent_only_once(mongo_db):
    doc = _make_criterion(deadline=datetime.now(timezone.utc) + timedelta(days=1))
    await repo.create_criterion(doc)

    assert await repo.mark_reminder_sent(doc.criterion_id) is True
    assert await repo.mark_reminder_sent(doc.criterion_id) is False


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    doc = _make_criterion()
    assert await repo.create_criterion(doc) is False
    assert await repo.get_by_id(doc.criterion_id) is None
    assert await repo.list_by_idea("idea_1") == []
    assert await repo.list_lapsable() == []
    assert await repo.resolve(doc.criterion_id, "met", None) is False
    assert await repo.mark_lapsed(doc.criterion_id) is False
    assert await repo.list_needing_reminder(within_days=3) == []
    assert await repo.mark_reminder_sent(doc.criterion_id) is False
