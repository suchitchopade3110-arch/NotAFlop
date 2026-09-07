"""
Phase 2 — the log surface (B1). Every route requires ownership: the
calling session created the idea, or (once claimed) it belongs to the
caller's account — see core.dependencies.get_owner_context and
repositories.idea_repository.owns. A missing idea and one the caller
doesn't own both return 404 rather than 403, so idea_ids can't be probed
to learn whether they exist under someone else's account.
"""
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import OwnerContext, get_owner_context
from core.ids import generate_share_token
from models.documents import IdeaDocument, SnapshotDocument
from models.schemas import (
    IdeaDetailResponse,
    IdeaSummary,
    PromoteIdeaRequest,
    SnapshotSummary,
    TimelineEntry,
)
from repositories import criteria_repository, evidence_repository, report_repository
from services import log_service, snapshot_worker
from services.rate_limiter import check_snapshot_rerun_rate_limit

router = APIRouter()


async def _get_owned_idea_or_404(idea_id: str, owner: OwnerContext) -> IdeaDocument:
    idea = await log_service.get_idea(idea_id)
    if idea is None or not log_service.owns_idea(idea, owner.session_id, owner.account_id):
        raise HTTPException(status_code=404, detail="Idea not found.")
    return idea


def _idea_detail(idea: IdeaDocument, snapshot: SnapshotDocument | None) -> IdeaDetailResponse:
    return IdeaDetailResponse(
        idea_id=idea.idea_id,
        raw_text=idea.raw_text,
        keyword=idea.keyword,
        status=idea.status,
        share_token=idea.share_token,
        current_snapshot_id=idea.current_snapshot_id,
        weights_version=snapshot.weights_version if snapshot else None,
        raw_score=snapshot.raw_score if snapshot else None,
        verdict=snapshot.verdict if snapshot else None,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
    )


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


@router.post("/ideas", response_model=IdeaDetailResponse, status_code=201)
async def promote_idea(body: PromoteIdeaRequest, owner: OwnerContext = Depends(get_owner_context)):
    """Promote a completed v1 validation run into a durable idea log.
    Only the session that generated the report may promote it (account
    ownership doesn't apply here yet — the report itself predates
    Phase 2's account concept)."""
    report = await report_repository.get_by_public_id(body.report_id)
    if report is None or report.session_id != owner.session_id:
        raise HTTPException(status_code=404, detail="Report not found.")

    idea = await log_service.promote_report_to_idea(
        report,
        session_id=owner.session_id,
        account_id=owner.account_id,
        share_token=generate_share_token(),
    )
    if idea is None:
        raise HTTPException(status_code=503, detail="Could not create idea log. Try again.")

    snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    return _idea_detail(idea, snapshot)


@router.get("/ideas", response_model=list[IdeaSummary])
async def list_ideas(owner: OwnerContext = Depends(get_owner_context)):
    ideas = await log_service.list_owned_ideas(owner.session_id, owner.account_id)

    summaries = []
    for idea in ideas:
        snapshot = await log_service.get_latest_snapshot(idea.idea_id)
        summaries.append(
            IdeaSummary(
                idea_id=idea.idea_id,
                keyword=idea.keyword,
                raw_score=snapshot.raw_score if snapshot else None,
                verdict=snapshot.verdict if snapshot else None,
                status=idea.status,
                last_snapshot_at=snapshot.created_at if snapshot else None,
                created_at=idea.created_at,
            )
        )
    return summaries


@router.get("/ideas/{idea_id}", response_model=IdeaDetailResponse)
async def get_idea(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    idea = await _get_owned_idea_or_404(idea_id, owner)
    snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    return _idea_detail(idea, snapshot)


@router.delete("/ideas/{idea_id}", status_code=204)
async def delete_idea(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    await _get_owned_idea_or_404(idea_id, owner)
    await log_service.delete_idea_cascade(idea_id)


@router.get("/ideas/{idea_id}/snapshots", response_model=list[SnapshotSummary])
async def list_snapshots(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    await _get_owned_idea_or_404(idea_id, owner)
    history = await log_service.get_snapshot_history(idea_id)
    return [_snapshot_summary(s) for s in history]


@router.post("/ideas/{idea_id}/snapshots", response_model=SnapshotSummary, status_code=201)
async def force_snapshot(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    """Force an immediate re-run — rate limited independently of the
    validation caps (services.rate_limiter.check_snapshot_rerun_rate_limit),
    scoped per idea. Runs the same always-eligible set a scheduled
    re-run would (data layer + Timing/TAM/Moat); it does not unlock the
    evidence-gated set."""
    idea = await _get_owned_idea_or_404(idea_id, owner)

    result = await check_snapshot_rerun_rate_limit(idea_id)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail={"limit": result.limit, "remaining": result.remaining, "scope": result.scope},
        )

    snapshot = await snapshot_worker.run_manual_snapshot(idea)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Could not complete re-run. Try again.")
    return _snapshot_summary(snapshot)


@router.get("/ideas/{idea_id}/timeline", response_model=list[TimelineEntry])
async def get_timeline(idea_id: str, owner: OwnerContext = Depends(get_owner_context)):
    """Merged, chronological feed across every Phase 2 event type for
    this idea — snapshots, evidence, kill-criteria, milestones."""
    idea = await _get_owned_idea_or_404(idea_id, owner)

    entries: list[TimelineEntry] = []

    for snapshot in await log_service.get_snapshot_history(idea_id):
        entries.append(
            TimelineEntry(
                type="snapshot",
                at=snapshot.created_at,
                payload={
                    "snapshot_id": snapshot.snapshot_id,
                    "trigger": snapshot.trigger,
                    "raw_score": snapshot.raw_score,
                    "verdict": snapshot.verdict,
                    "deltas": snapshot.deltas,
                    "version_crossing": snapshot.version_crossing,
                },
            )
        )

    for evidence in await evidence_repository.list_by_idea(idea_id):
        entries.append(
            TimelineEntry(
                type="evidence",
                at=evidence.submitted_at,
                payload={
                    "evidence_id": evidence.evidence_id,
                    "evidence_type": evidence.type,
                    "triggered_snapshot_id": evidence.triggered_snapshot_id,
                },
            )
        )

    for criterion in await criteria_repository.list_by_idea(idea_id):
        entries.append(
            TimelineEntry(
                type="criterion",
                at=criterion.resolved_at or criterion.created_at,
                payload={
                    "criterion_id": criterion.criterion_id,
                    "statement": criterion.statement,
                    "status": criterion.status,
                    "deadline": criterion.deadline.isoformat(),
                },
            )
        )

    for milestone in idea.milestones:
        entries.append(
            TimelineEntry(
                type="milestone",
                at=milestone.completed_at or milestone.created_at,
                payload={
                    "milestone_id": milestone.milestone_id,
                    "block_title": milestone.block_title,
                    "completed": milestone.completed,
                },
            )
        )

    entries.sort(key=lambda entry: entry.at)
    return entries
