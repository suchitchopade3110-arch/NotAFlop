"""
Internal/admin-only endpoints. Not part of the founder-facing API surface
— gated by core.dependencies.require_admin (an X-Admin-Key header checked
against core.config.ADMIN_API_KEY), never by session/rate-limit context.
"""
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import require_admin
from models.schemas import RescoreRequest, RescoreResponse, RescoreResult, VerifierDivergenceStats
from repositories import report_repository
from services import log_service, rescore_service
from services.gate import WEIGHTS_VERSION

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/verifier/stats", response_model=VerifierDivergenceStats)
async def verifier_stats():
    """Shadow-mode divergence between raw_score and adjusted_score across
    every persisted report that has a Verifier result — count, mean
    absolute delta, max delta, and a bucketed distribution. Read-only: it
    does not gate or alter anything, and VERIFIER_PENALTY_ENABLED stays
    the single switch that decides whether the Verifier affects a verdict.
    """
    stats = await report_repository.get_verifier_divergence_stats()
    return VerifierDivergenceStats(**stats)


@router.post("/rescore", response_model=RescoreResponse)
async def rescore(body: RescoreRequest):
    """Phase 2, C7 — retroactive re-scoring by the current
    services.gate.WEIGHTS_VERSION. Writes a new snapshot per affected
    idea (services.log_service.record_snapshot); never mutates a
    historical one. Pass idea_id to re-score a single idea, or omit it
    to sweep every active idea."""
    if body.idea_id:
        idea = await log_service.get_idea(body.idea_id)
        if idea is None:
            raise HTTPException(status_code=404, detail="Idea not found.")
        status, snapshot_id = await rescore_service.rescore_idea(idea)
        results = [RescoreResult(idea_id=idea.idea_id, snapshot_id=snapshot_id, status=status)]
    else:
        results = [
            RescoreResult(idea_id=idea_id, snapshot_id=snapshot_id, status=status)
            for idea_id, status, snapshot_id in await rescore_service.rescore_all_active()
        ]

    return RescoreResponse(weights_version=WEIGHTS_VERSION, results=results)
