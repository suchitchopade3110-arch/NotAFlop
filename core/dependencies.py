"""
Cross-cutting FastAPI dependencies applied at the route level (not
middleware) — so they only run on the endpoints that opt in.
"""
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException

from core.config import ADMIN_API_KEY
from core.session import SESSION_HEADER, SessionContext, get_session_context
from repositories import session_repository
from services.rate_limiter import check_rate_limit

ADMIN_KEY_HEADER = "X-Admin-Key"


async def enforce_rate_limit(session: SessionContext = Depends(get_session_context)) -> SessionContext:
    """Applied only to generation endpoints. Raises 429 with a structured
    body when either the session or ip cap is exceeded.

    Headers set on the dependency-injected Response inside
    get_session_context are dropped when a dependency raises — FastAPI
    only merges those into the response on the success path. Passing
    X-Session-Id via HTTPException's own headers= keeps it present even
    on a 429, which matters when a brand-new session trips the ip cap on
    its very first request and would otherwise never learn its own id.
    """
    result = await check_rate_limit(session.session_id, session.ip)

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "limit": result.limit,
                "remaining": result.remaining,
                "reset_at": datetime.fromtimestamp(result.reset_at, tz=timezone.utc).isoformat(),
                "scope": result.scope,
            },
            headers={SESSION_HEADER: session.session_id},
        )

    return session


@dataclass(frozen=True)
class OwnerContext:
    """Session identity plus whatever account it's currently bound to
    (Phase 2, A4) — the shape every /v1/ideas/* and related route needs
    for ownership checks (repositories.idea_repository.owns). Anonymous
    (unclaimed) callers get account_id=None, exactly like today."""

    session_id: str
    account_id: str | None
    ip: str


async def get_owner_context(session: SessionContext = Depends(get_session_context)) -> OwnerContext:
    session_doc = await session_repository.get_session(session.session_id)
    account_id = session_doc.account_id if session_doc else None
    return OwnerContext(session_id=session.session_id, account_id=account_id, ip=session.ip)


async def require_admin(x_admin_key: str | None = Header(default=None, alias=ADMIN_KEY_HEADER)) -> None:
    """Applied only to /internal endpoints. Fails closed: an unconfigured
    ADMIN_API_KEY means the route always 503s rather than ever being
    reachable with no credential to check. Constant-time comparison so a
    correctly-shaped but wrong key can't be brute-forced via timing."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin API is not configured.")

    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing admin credentials.")
