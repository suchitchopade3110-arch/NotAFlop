from fastapi import APIRouter, HTTPException
from models.schemas import GateRequest, GateResponse
from services.gate import compute_gate

router = APIRouter()


@router.post("/gate", response_model=GateResponse)
async def gate(body: GateRequest):
    """
    Clean verdict API. Takes Phase 3's agent results and returns
    a re-computable score, verdict, top risks, and one-sentence gate reason.

    Re-derives the verdict from raw agent scores rather than trusting a
    client-supplied score, so this endpoint is safe to call independently
    of the Phase 3 SSE stream (e.g. for re-scoring, audits, or the
    No-Go Share Hook / Pivot Classifier consuming this later).
    """
    if not body.results:
        raise HTTPException(status_code=400, detail="No agent results supplied.")

    return compute_gate(body.results)
