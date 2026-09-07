"""
Anonymous session identity. Sessions are server-minted: a request without
X-Session-Id gets a fresh one, which is echoed back via the same response
header for the (future) frontend to store and resend.
"""
from dataclasses import dataclass

import structlog
from fastapi import Request, Response

from core.ids import generate_session_id
from repositories import session_repository

SESSION_HEADER = "X-Session-Id"


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    ip: str


def extract_client_ip(request: Request) -> str:
    """Client IP for session records and the rate limiter's IP backstop
    (services.rate_limiter) — the IP cap is only load-bearing if this
    returns the real originating client, since the session cap alone is
    trivially bypassed by clearing local storage to mint a fresh session.

    Deployment-topology assumption: exactly one trusted reverse proxy
    (load balancer / nginx / cloud LB) sits in front of this app and is
    the only thing allowed to set X-Forwarded-For — it either overwrites
    any client-supplied value or appends the real client IP as the first
    hop, so the LEFTMOST entry in the header is the true origin client.
    This holds for a standard single-LB deployment but is NOT safe if:
      - the app is reachable directly from the internet (no proxy in
        front of it) — a client can set X-Forwarded-For to anything and
        this function will trust it, silently defeating the IP cap; or
      - multiple chained proxies sit in front of it and any of them
        forward a client-supplied XFF value instead of overwriting it —
        the leftmost entry is then attacker-controlled, not proxy-set.
    If either applies, fix the proxy config to strip/overwrite inbound
    X-Forwarded-For before it reaches this app rather than changing which
    entry this function reads.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_session_context(request: Request, response: Response) -> SessionContext:
    session_id = request.headers.get(SESSION_HEADER) or generate_session_id()
    response.headers[SESSION_HEADER] = session_id
    # C2: every log line for the rest of this request now carries
    # session_id — see core/logging.py's module docstring.
    structlog.contextvars.bind_contextvars(session_id=session_id)

    ip = extract_client_ip(request)
    await session_repository.get_or_create_session(session_id, ip)

    return SessionContext(session_id=session_id, ip=ip)
