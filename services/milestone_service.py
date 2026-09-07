"""
Stateful milestone tracking (C4). GET /v1/ideas/{id}/milestones seeds
an idea's milestone list from Phase 5's roadmap generator
(services.plan.generate_roadmap — untouched, reused as-is, no scoring
weights or agent prompts involved) the FIRST time it's called for a
given idea, then every call after that reads back the persisted,
possibly-completed state. PATCH /v1/milestones/{mid} is the only thing
that ever mutates it past that one-time seed.
"""
from datetime import datetime, timezone

from core.ids import generate_milestone_id
from models.documents import MilestoneRecord
from models.schemas import PlanRequest
from repositories import idea_repository
from services.plan import generate_roadmap


async def get_or_seed_milestones(idea) -> list[MilestoneRecord]:
    if idea.milestones:
        return idea.milestones

    request = PlanRequest(report_id=idea.source_report_id or idea.idea_id, idea_summary=idea.raw_text)
    roadmap = generate_roadmap(request, idea.raw_text, top_risks=[])
    milestones = [
        MilestoneRecord(
            milestone_id=generate_milestone_id(),
            day_range=block.day_range,
            block_title=block.block_title,
            tasks=block.tasks,
            deliverable=block.deliverable,
        )
        for block in roadmap
    ]
    await idea_repository.set_milestones(idea.idea_id, milestones)
    return milestones


async def patch_milestone(
    idea_id: str, milestone_id: str, completed: bool, evidence_id: str | None
) -> bool:
    fields: dict = {"completed": completed, "completed_at": datetime.now(timezone.utc) if completed else None}
    if evidence_id is not None:
        fields["evidence_id"] = evidence_id
    return await idea_repository.update_milestone(idea_id, milestone_id, **fields)
