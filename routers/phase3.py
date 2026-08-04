from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.dependencies import enforce_rate_limit
from core.session import SESSION_HEADER, SessionContext
from orchestrator.graph import stream_analysis

from services.keyword_extractor import extract_keyword, KeywordExtractionError

router = APIRouter()


class AnalyzeRequest(BaseModel):
    transcript: str
    keyword: str | None = None
    signals: dict                      # from Phase 2 smart data layer
    filter_result: dict | None = None  # Phase 1 result, persisted alongside the report if supplied


@router.post("/analyze")
async def analyze(body: AnalyzeRequest, session: SessionContext = Depends(enforce_rate_limit)):
    """
    Stream Phase 3 agent results via SSE.
    Each agent emits a JSON event as it completes.
    Final event contains the aggregated score + verdict.

    SSE event types:
      { type: "agent",       payload: AgentOutput }
      { type: "agent_error", payload: { agent, error } }
      { type: "final",       payload: { public_id, score, verdict, errors } }
      [DONE]

    Rate limited: 3/day per session (primary), 15/day per ip (cost
    backstop). Exceeding either returns 429 with a structured body
    (limit, remaining, reset_at, scope) — see models.schemas.RateLimitError.
    """
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")

    # TODO: Revisit making filter_result required once frontend reliably passes it on every call.
    if body.filter_result and body.filter_result.get("verdict") == "fail":
        raise HTTPException(
            status_code=422,
            detail=(
                "This pitch didn't pass Phase 1 filtering "
                f"({body.filter_result.get('feedback', 'clarity or problem specificity too weak')}). "
                "Revise the pitch and re-run Phase 1 before analyzing."
            ),
        )

    keyword = (body.keyword or "").strip()
    if not keyword:
        try:
            keyword = await extract_keyword(body.transcript)
        except KeywordExtractionError:
            raise HTTPException(
                status_code=422,
                detail="couldn't extract a clear topic from this pitch — try being more specific",
            )

    # The endpoint returns its own StreamingResponse, so headers set on the
    # dependency-injected Response (inside get_session_context) never make
    # it to the client — FastAPI only merges those for responses it builds
    # itself. Set X-Session-Id again here, on the response actually sent.
    return StreamingResponse(
        stream_analysis(
            body.transcript,
            keyword,
            body.signals,
            session_id=session.session_id,
            ip=session.ip,
            filter_result=body.filter_result,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
            SESSION_HEADER: session.session_id,
        },
    )
