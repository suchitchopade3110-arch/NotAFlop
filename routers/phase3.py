from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.session import SessionContext, get_session_context
from orchestrator.graph import stream_analysis

router = APIRouter()


class AnalyzeRequest(BaseModel):
    transcript: str
    keyword: str
    signals: dict                      # from Phase 2 smart data layer
    filter_result: dict | None = None  # Phase 1 result, persisted alongside the report if supplied


@router.post("/analyze")
async def analyze(body: AnalyzeRequest, session: SessionContext = Depends(get_session_context)):
    """
    Stream Phase 3 agent results via SSE.
    Each agent emits a JSON event as it completes.
    Final event contains the aggregated score + verdict.

    SSE event types:
      { type: "agent",       payload: AgentOutput }
      { type: "agent_error", payload: { agent, error } }
      { type: "final",       payload: { score, verdict, errors } }
      [DONE]
    """
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    if not body.keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is empty.")

    return StreamingResponse(
        stream_analysis(
            body.transcript,
            body.keyword,
            body.signals,
            session_id=session.session_id,
            ip=session.ip,
            filter_result=body.filter_result,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
        },
    )
