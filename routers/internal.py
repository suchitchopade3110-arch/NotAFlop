"""
Internal/admin-only endpoints. Not part of the founder-facing API surface
— gated by core.dependencies.require_admin (an X-Admin-Key header checked
against core.config.ADMIN_API_KEY), never by session/rate-limit context.
"""
from fastapi import APIRouter, Depends

from core.dependencies import require_admin
from models.schemas import VerifierDivergenceStats
from repositories import report_repository

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
