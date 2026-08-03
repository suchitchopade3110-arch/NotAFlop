"""
Phase 5 - Plan & Build
routers/phase5.py - thin router for 90-day roadmap generation.
"""

from fastapi import APIRouter, HTTPException
from models.schemas import PlanRequest, PlanResponse
from repositories import report_repository
from services.plan import generate_plan

router = APIRouter()


@router.post("/plan", response_model=PlanResponse)
async def create_plan(body: PlanRequest) -> PlanResponse:
    """
    Takes a persisted report_id, verifies that tier_reached >= 2 (Phase 4 score >= 50),
    and returns a 90-day roadmap + team recommendation.
    """
    doc = await report_repository.get_by_public_id(body.report_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    if doc.tier_reached < 2:
        raise HTTPException(
            status_code=403,
            detail="Phase 5 roadmap is locked for ideas scoring below 50 in Phase 4 gate.",
        )

    idea_summary = (body.idea_summary or doc.transcript).strip()

    top_risks = [
        f"{record.agent}: {record.feedback}"
        for record in doc.agent_results.values()
        if not record.passed or record.score < 6
    ]

    return generate_plan(body, idea_summary=idea_summary, top_risks=top_risks)
