"""
Cross-cutting FastAPI dependencies applied at the route level (not
middleware) — so they only run on the endpoints that opt in.
"""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from core.session import SessionContext, get_session_context
from services.rate_limiter import check_rate_limit


async def enforce_rate_limit(session: SessionContext = Depends(get_session_context)) -> SessionContext:
    """Applied only to generation endpoints. Raises 429 with a structured
    body when either the session or ip cap is exceeded."""
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
        )

    return session
