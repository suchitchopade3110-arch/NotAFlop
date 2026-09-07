from models.documents import IdeaDocument, MilestoneRecord
from repositories import idea_repository as repo


def _make_idea(idea_id="idea_0000000001", session_id="sess1", account_id=None, share_token="tok1") -> IdeaDocument:
    return IdeaDocument(
        idea_id=idea_id,
        session_id=session_id,
        account_id=account_id,
        idea_hash="hash1",
        raw_text="Uber for dog walking",
        normalized_text="uber for dog walking",
        share_token=share_token,
    )


async def test_create_and_get_by_id(mongo_db):
    doc = _make_idea()
    assert await repo.create_idea(doc) is True

    fetched = await repo.get_by_id(doc.idea_id)
    assert fetched is not None
    assert fetched.idea_hash == "hash1"
    assert fetched.account_id is None
    assert fetched.status == "active"


async def test_get_by_share_token(mongo_db):
    doc = _make_idea()
    await repo.create_idea(doc)
    fetched = await repo.get_by_share_token("tok1")
    assert fetched is not None
    assert fetched.idea_id == doc.idea_id


async def test_same_idea_hash_two_independent_ideas(mongo_db):
    """A2: idea_hash is an index only, never a short-circuit — two
    founders (or the same founder twice) pitching the same text each get
    their own document and independent history."""
    doc1 = _make_idea(idea_id="idea_0000000001", session_id="s1", share_token="tokA")
    doc2 = _make_idea(idea_id="idea_0000000002", session_id="s2", share_token="tokB")
    await repo.create_idea(doc1)
    await repo.create_idea(doc2)

    owned_s1 = await repo.list_owned("s1", None)
    owned_s2 = await repo.list_owned("s2", None)
    assert {i.idea_id for i in owned_s1} == {"idea_0000000001"}
    assert {i.idea_id for i in owned_s2} == {"idea_0000000002"}


async def test_list_owned_excludes_deleted(mongo_db):
    doc = _make_idea()
    await repo.create_idea(doc)
    await repo.delete_idea(doc.idea_id)
    assert await repo.list_owned("sess1", None) == []


def test_owns_anonymous_session_match():
    idea = _make_idea()
    assert repo.owns(idea, "sess1", None) is True
    assert repo.owns(idea, "other-session", None) is False


def test_owns_claimed_idea_requires_account_match():
    idea = _make_idea(account_id="acct_1")
    # Same original session, but idea is now claimed — session alone no
    # longer proves ownership.
    assert repo.owns(idea, "sess1", None) is False
    assert repo.owns(idea, "sess1", "acct_1") is True
    assert repo.owns(idea, "sess1", "acct_2") is False


async def test_set_current_snapshot(mongo_db):
    doc = _make_idea()
    await repo.create_idea(doc)
    assert await repo.set_current_snapshot(doc.idea_id, "snap_1") is True

    fetched = await repo.get_by_id(doc.idea_id)
    assert fetched.current_snapshot_id == "snap_1"


async def test_transfer_to_account_only_touches_unclaimed(mongo_db):
    already_claimed = _make_idea(idea_id="idea_0000000003", session_id="sess1", account_id="acct_other", share_token="tokC")
    unclaimed = _make_idea(idea_id="idea_0000000004", session_id="sess1", share_token="tokD")
    await repo.create_idea(already_claimed)
    await repo.create_idea(unclaimed)

    moved = await repo.transfer_to_account("sess1", "acct_new")
    assert moved == 1

    fetched = await repo.get_by_id("idea_0000000004")
    assert fetched.account_id == "acct_new"
    still_other = await repo.get_by_id("idea_0000000003")
    assert still_other.account_id == "acct_other"


async def test_set_and_update_milestones(mongo_db):
    doc = _make_idea()
    await repo.create_idea(doc)
    milestones = [
        MilestoneRecord(milestone_id="mile_1", day_range="Day 1-30", block_title="MVP", deliverable="Working MVP"),
    ]
    assert await repo.set_milestones(doc.idea_id, milestones) is True

    assert await repo.update_milestone(doc.idea_id, "mile_1", completed=True) is True
    fetched = await repo.get_by_id(doc.idea_id)
    assert fetched.milestones[0].completed is True

    assert await repo.update_milestone(doc.idea_id, "does-not-exist", completed=True) is False


async def test_delete_idea(mongo_db):
    doc = _make_idea()
    await repo.create_idea(doc)
    assert await repo.delete_idea(doc.idea_id) is True
    assert await repo.get_by_id(doc.idea_id) is None
    assert await repo.delete_idea(doc.idea_id) is False


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    doc = _make_idea()
    assert await repo.create_idea(doc) is False
    assert await repo.get_by_id(doc.idea_id) is None
    assert await repo.get_by_share_token("tok1") is None
    assert await repo.list_owned("sess1", None) == []
    assert await repo.set_current_snapshot(doc.idea_id, "snap_1") is False
    assert await repo.delete_idea(doc.idea_id) is False
    assert await repo.transfer_to_account("sess1", "acct_1") == 0
