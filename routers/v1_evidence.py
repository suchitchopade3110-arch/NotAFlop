"""
Phase 2 — evidence and milestones (C4). POST /v1/ideas/{id}/evidence and
GET /v1/ideas/{id}/milestones are idea-scoped, ownership-checked like
every B1 route; PATCH /v1/milestones/{mid} is addressed by the
milestone's own id, so it's resolved by scanning the caller's OWN ideas
(never a global scan — milestones are embedded, not their own indexed
collection, see A1/A2).
"""
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import OwnerContext, get_owner_context
from models.documents import IdeaDocument, MilestoneRecord, SnapshotDocument
from models.schemas import (
    EvidenceRequest,
    EvidenceResponse,
    MilestonePatchRequest,
    MilestoneResponse,
    SnapshotSummary,
)
from repositories import evidence_repository
from services import evidence_service, log_service, milestone_service

router = APIRouter()


async def _get_owned_idea_or_404(idea_id: str, owner: OwnerContext) -> IdeaDocument:
    idea = await log_service.get_idea(idea_id)
    if idea is None or not log_service.owns_idea(idea, owner.session_id, owner.account_id):
        raise HTTPException(status_code=404, detail="Idea not found.")
    return idea


def _snapshot_summary(snapshot: SnapshotDocument) -> SnapshotSummary:
    return SnapshotSummary(
        snapshot_id=snapshot.snapshot_id,
        trigger=snapshot.trigger,
        raw_score=snapshot.raw_score,
        verdict=snapshot.verdict,
        weights_version=snapshot.weights_version,
        deltas=snapshot.deltas,
        version_crossing=snapshot.version_crossing,
        cost=snapshot.cost,
        created_at=snapshot.created_at,
    )


def _milestone_response(m: MilestoneRecord) -> MilestoneResponse:
    return MilestoneResponse(
        milestone_id=m.milestone_id,
        day_range=m.day_range,
        block_title=m.block_title,
        tasks=m.tasks,
        deliverable=m.deliverable,
        completed=m.completed,
        completed_at=m.completed_at,
        evidence_id=m.evidence_id,
    )


@router.post("/ideas/{idea_id}/evidence", response_model=EvidenceResponse, status_code=201)
async def submit_evidence(
    idea_id: str, body: EvidenceRequest, owner: OwnerContext = Depends(get_owner_context)
):
    idea = await _get_owned_idea_or_404(idea_id, owner)
    result = await evidence_service.submit_evidence(idea, body)
    if result is None:
        raise HTTPException(status_code=503, detail="Could not save evidence. Try again.")

    evidence, snapshot = result
    return EvidenceResponse(
        evidence_id=evidence.evidence_id,
        idea_id=evidence.idea_id,
        type=evidence.type,
        payload=evidence.payload,
        submitted_at=evidence.submitted_at,
        triggered_snapshot_id=evidence.triggered_snapshot_id,
        snapshot=_snapshot_summary(snapshot) if snapshot else None,
    )


@router.get("/ideas/{idea_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    idea = await _get_owned_idea_or_404(idea_id, owner)
    milestones = await milestone_service.get_or_seed_milestones(idea)
    return [_milestone_response(m) for m in milestones]


@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponse)
async def patch_milestone(
    milestone_id: str, body: MilestonePatchRequest, owner: OwnerContext = Depends(get_owner_context)
):
    ideas = await log_service.list_owned_ideas(owner.session_id, owner.account_id)
    target_idea: IdeaDocument | None = None
    for idea in ideas:
        if any(m.milestone_id == milestone_id for m in idea.milestones):
            target_idea = idea
            break

    if target_idea is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")

    if body.evidence_id is not None:
        evidence = await evidence_repository.get_by_id(body.evidence_id)
        if evidence is None or evidence.idea_id != target_idea.idea_id:
            raise HTTPException(status_code=400, detail="evidence_id does not belong to this idea.")

    ok = await milestone_service.patch_milestone(
        target_idea.idea_id, milestone_id, body.completed, body.evidence_id
    )
    if not ok:
        raise HTTPException(status_code=503, detail="Could not update milestone.")

    updated_idea = await log_service.get_idea(target_idea.idea_id)
    updated = next(m for m in updated_idea.milestones if m.milestone_id == milestone_id)
    return _milestone_response(updated)
