"""
Anonymous session identity. Sessions are server-minted: a request without
X-Session-Id gets a fresh one, which is echoed back via the same response
header for the (future) frontend to store and resend.
"""
from dataclasses import dataclass

from fastapi import Request, Response

from core.ids import generate_session_id
from repositories import session_repository

SESSION_HEADER = "X-Session-Id"


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    ip: str


def extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_session_context(request: Request, response: Response) -> SessionContext:
    session_id = request.headers.get(SESSION_HEADER) or generate_session_id()
    response.headers[SESSION_HEADER] = session_id

    ip = extract_client_ip(request)
    await session_repository.get_or_create_session(session_id, ip)

    return SessionContext(session_id=session_id, ip=ip)
