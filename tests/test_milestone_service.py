from models.documents import IdeaDocument
from services import milestone_service


def _make_idea() -> IdeaDocument:
    return IdeaDocument(
        idea_id="idea_milestone1",
        session_id="sess1",
        idea_hash="h1",
        raw_text="A marketplace connecting freelance vets with pet owners for on-demand house calls.",
        normalized_text="a marketplace...",
        share_token="tok_mile",
    )


async def test_seeds_milestones_from_roadmap_generator(mongo_db):
    idea = _make_idea()
    from repositories import idea_repository

    await idea_repository.create_idea(idea)

    milestones = await milestone_service.get_or_seed_milestones(idea)
    assert len(milestones) == 3
    assert all(m.milestone_id for m in milestones)
    assert all(m.completed is False for m in milestones)

    persisted = await idea_repository.get_by_id(idea.idea_id)
    assert len(persisted.milestones) == 3


async def test_does_not_reseed_once_present(mongo_db):
    from repositories import idea_repository

    idea = _make_idea()
    await idea_repository.create_idea(idea)

    first = await milestone_service.get_or_seed_milestones(idea)
    idea_after = await idea_repository.get_by_id(idea.idea_id)
    second = await milestone_service.get_or_seed_milestones(idea_after)

    assert [m.milestone_id for m in first] == [m.milestone_id for m in second]


async def test_patch_milestone_marks_complete(mongo_db):
    from repositories import idea_repository

    idea = _make_idea()
    await idea_repository.create_idea(idea)
    milestones = await milestone_service.get_or_seed_milestones(idea)
    target = milestones[0]

    ok = await milestone_service.patch_milestone(idea.idea_id, target.milestone_id, True, "ev_123")
    assert ok is True

    persisted = await idea_repository.get_by_id(idea.idea_id)
    updated = next(m for m in persisted.milestones if m.milestone_id == target.milestone_id)
    assert updated.completed is True
    assert updated.completed_at is not None
    assert updated.evidence_id == "ev_123"
