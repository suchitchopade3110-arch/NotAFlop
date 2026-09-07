"""
Progressive identity (Phase 2, A4). Claiming is offered only AFTER a
report has already streamed and been persisted — nothing in this router
runs on, or adds an auth requirement to, the validation path
(/api/phase1/filter, /api/phase3/analyze, /api/phase2/validate stay
exactly as they are; this whole router is opt-in and additive under /v1).

No password: a magic link is the only credential. /auth/claim issues a
single-use, short-TTL token (services.auth_tokens) and sends it through
the pluggable notification service (services.notifications — C6),
default provider logs it rather than actually emailing.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from core.config import FRONTEND_BASE_URL
from core.ids import generate_account_id
from core.logging import get_logger
from core.session import SessionContext, extract_client_ip, get_session_context
from models.documents import AccountDocument
from models.schemas import (
    ClaimRequest,
    ClaimResponse,
    MeResponse,
    SessionResponse,
    VerifyRequest,
    VerifyResponse,
)
from repositories import account_repository, session_repository
from services import auth_tokens, log_service
from services.notifications import service as notifications

router = APIRouter()
logger = get_logger("notaflop.routers.auth")


@router.post("/session", response_model=SessionResponse)
async def create_session(session: SessionContext = Depends(get_session_context)):
    """Mints (or echoes back) an anonymous session. Equivalent to what
    every other /v1 route already does via get_session_context — this
    endpoint exists so a client can explicitly obtain a session_id up
    front, before the founder has typed a single word of their pitch."""
    return SessionResponse(session_id=session.session_id)


@router.post("/auth/claim", response_model=ClaimResponse)
async def claim(
    body: ClaimRequest, request: Request, session: SessionContext = Depends(get_session_context)
):
    ip = extract_client_ip(request)

    email_ok = await auth_tokens.check_and_record_rate_limit("email", body.email)
    ip_ok = await auth_tokens.check_and_record_rate_limit("ip", ip)
    if not email_ok or not ip_ok:
        raise HTTPException(status_code=429, detail="Too many claim requests. Try again later.")

    token = await auth_tokens.issue_token(body.email, session.session_id)

    link = f"{FRONTEND_BASE_URL}/claim?token={token}"
    await notifications.send_magic_link(body.email, link)
    # Router-level trace only (never founder-facing) — the notification
    # service itself is what "sends" the link, default provider or real.
    logger.info("magic_link_issued", status="dispatched", link=link)

    return ClaimResponse(status="sent")


@router.post("/auth/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest):
    redeemed = await auth_tokens.redeem_token(body.token)
    if redeemed is None:
        raise HTTPException(status_code=400, detail="Invalid or expired claim token.")

    email = redeemed["email"]
    session_id = redeemed["session_id"]

    account = await account_repository.get_by_email(email)
    if account is None:
        account = AccountDocument(account_id=generate_account_id(), email=email)
        if not await account_repository.create_account(account):
            # Lost a create race to a concurrent verify for the same
            # email, or a transient Mongo hiccup — re-read rather than
            # fail a legitimate claim.
            account = await account_repository.get_by_email(email)
            if account is None:
                raise HTTPException(status_code=503, detail="Could not create account. Please try again.")

    await account_repository.add_session_id(account.account_id, session_id)
    await session_repository.set_account_id(session_id, account.account_id)
    claimed = await log_service.claim_ideas(session_id, account.account_id)

    return VerifyResponse(
        account_id=account.account_id,
        email=account.email,
        session_id=session_id,
        claimed_ideas=claimed,
    )


@router.get("/me", response_model=MeResponse)
async def me(session: SessionContext = Depends(get_session_context)):
    session_doc = await session_repository.get_session(session.session_id)
    account = None
    if session_doc and session_doc.account_id:
        account = await account_repository.get_by_id(session_doc.account_id)

    owned = await log_service.list_owned_ideas(
        session.session_id, account.account_id if account else None
    )

    return MeResponse(
        session_id=session.session_id,
        account_id=account.account_id if account else None,
        email=account.email if account else None,
        plan=account.plan if account else None,
        owned_idea_count=len(owned),
        report_count=session_doc.report_count if session_doc else 0,
    )
