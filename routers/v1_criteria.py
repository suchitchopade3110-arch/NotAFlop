"""
Phase 2 — kill-criteria loop (C3). POST/GET /v1/ideas/{id}/criteria are
idea-scoped and ownership-checked like every B1 route; POST
/v1/criteria/{cid}/resolve is addressed by the criterion's own id, so
ownership is checked via the criterion's parent idea.
"""
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import OwnerContext, get_owner_context
from models.documents import CriterionDocument, IdeaDocument
from models.schemas import CriterionRequest, CriterionResponse, ResolveCriterionRequest
from repositories import criteria_repository
from services import criteria_service, log_service, scheduler

router = APIRouter()

# Registered once, at import time (module caching guarantees this runs
# exactly once per process) — the scheduler loop (services/scheduler.py,
# off by default) picks this up alongside the snapshot sweep it already
# runs every tick.
scheduler.register_sweep(criteria_service.sweep_lapsed_criteria)
scheduler.register_sweep(criteria_service.sweep_deadline_reminders)


def _to_response(criterion: CriterionDocument) -> CriterionResponse:
    return CriterionResponse(
        criterion_id=criterion.criterion_id,
        idea_id=criterion.idea_id,
        statement=criterion.statement,
        metric=criterion.metric,
        threshold=criterion.threshold,
        deadline=criterion.deadline,
        status=criterion.status,
        resolved_at=criterion.resolved_at,
        resolution_note=criterion.resolution_note,
        created_at=criterion.created_at,
    )


async def _get_owned_idea_or_404(idea_id: str, owner: OwnerContext) -> IdeaDocument:
    idea = await log_service.get_idea(idea_id)
    if idea is None or not log_service.owns_idea(idea, owner.session_id, owner.account_id):
        raise HTTPException(status_code=404, detail="Idea not found.")
    return idea


@router.post("/ideas/{idea_id}/criteria", response_model=CriterionResponse, status_code=201)
async def create_criterion(
    idea_id: str, body: CriterionRequest, owner: OwnerContext = Depends(get_owner_context)
):
    """Vague statements are rejected before this handler ever runs —
    CriterionRequest's own field_validators (models/schemas.py) enforce
    a non-trivial statement/metric/threshold and a future deadline. A
    commitment that cannot fail is not a commitment."""
    idea = await _get_owned_idea_or_404(idea_id, owner)
    criterion = await criteria_service.create_criterion(idea, body)
    if criterion is None:
        raise HTTPException(status_code=503, detail="Could not save criterion. Try again.")
    return _to_response(criterion)


@router.get("/ideas/{idea_id}/criteria", response_model=list[CriterionResponse])
async def list_criteria(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    await _get_owned_idea_or_404(idea_id, owner)
    criteria = await criteria_service.list_criteria(idea_id)
    return [_to_response(c) for c in criteria]


@router.post("/criteria/{criterion_id}/resolve", response_model=CriterionResponse)
async def resolve_criterion(
    criterion_id: str, body: ResolveCriterionRequest, owner: OwnerContext = Depends(get_owner_context)
):
    criterion = await criteria_repository.get_by_id(criterion_id)
    if criterion is None:
        raise HTTPException(status_code=404, detail="Criterion not found.")

    idea = await _get_owned_idea_or_404(criterion.idea_id, owner)

    if criterion.status != "pending":
        raise HTTPException(status_code=409, detail=f"Criterion already {criterion.status}.")

    result = await criteria_service.resolve_criterion(criterion, idea, body.outcome, body.note)
    if result is None:
        raise HTTPException(status_code=503, detail="Could not resolve criterion. Try again.")

    resolved, _evidence = result
    return _to_response(resolved)
