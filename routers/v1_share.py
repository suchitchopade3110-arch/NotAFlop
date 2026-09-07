"""
Phase 2 — the No-Go Share Hook (B2). Public, no-auth, read-only verdict
card. Never returns raw pitch text, email, or evidence payloads — see
services/share.py's module docstring for why that's structural, not
just a field allowlist here.
"""
from fastapi import APIRouter, HTTPException, Request

from core.session import extract_client_ip
from models.schemas import ShareCardResponse
from services import log_service, share
from services.rate_limiter import check_share_card_rate_limit

router = APIRouter()


@router.get("/share/{token}", response_model=ShareCardResponse)
async def get_share_card(token: str, request: Request):
    ip = extract_client_ip(request)
    result = await check_share_card_rate_limit(ip)
    if not result.allowed:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    idea = await log_service.get_idea_by_share_token(token)
    if idea is None or idea.status == "deleted":
        raise HTTPException(status_code=404, detail="Not found.")

    snapshot = await log_service.get_latest_snapshot(idea.idea_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Not found.")

    return ShareCardResponse(
        verdict=snapshot.verdict,
        raw_score=snapshot.raw_score,
        keyword=idea.keyword,
        top_reasons=share.top_reasons(snapshot.agent_scores, snapshot.verdict),
        created_at=snapshot.created_at,
    )
