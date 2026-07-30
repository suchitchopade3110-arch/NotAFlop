from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from models.documents import AgentResultRecord, VerifierOutput


# ── Transcribe ────────────────────────────────────────────────
class TranscribeResponse(BaseModel):
    transcript: str


# ── Filter ────────────────────────────────────────────────────
class FilterRequest(BaseModel):
    transcript: str


class AgentResult(BaseModel):
    passed: bool
    score: int          # 0-10
    feedback: str       # one-sentence verdict


class FilterResponse(BaseModel):
    verdict: str                    # "pass" | "fail"
    narrow_problem: AgentResult
    pitch_clarity: AgentResult
    feedback: str | None = None     # populated only on fail


# ── Gate (Phase 4) ───────────────────────────────────────────
class GateRequest(BaseModel):
    results: dict                   # dict[str, AgentOutput] from Phase 3


class RiskItem(BaseModel):
    agent: str
    score: int
    feedback: str


class GateResponse(BaseModel):
    score: int                      # 0-100
    verdict: str                    # "go" | "pivot" | "no-go"
    top_risks: list[RiskItem]
    gate_reason: str


# ── Reports (persistence) ────────────────────────────────────
class ReportResponse(BaseModel):
    """GET /reports/{public_id}. session_id/ip are intentionally omitted
    — the public link should not expose who generated the report."""

    public_id: str
    idea_hash: str
    transcript: str
    keyword: str
    signals: dict
    filter_result: dict | None = None

    agent_results: dict[str, AgentResultRecord]
    verifier: VerifierOutput | None = None

    weights_version: int
    raw_score: int
    adjusted_score: int | None = None
    verdict: str
    gating_score: Literal["raw", "adjusted"]
    verdict_would_flip: bool
    tier_reached: int

    created_at: datetime
    updated_at: datetime


class ReportSummary(BaseModel):
    """One row of GET /sessions/{sid}/reports — light enough for a list view."""

    public_id: str
    keyword: str
    raw_score: int
    verdict: str
    tier_reached: int
    created_at: datetime


class RateLimitError(BaseModel):
    """Body of a 429 from the rate-limit dependency."""

    limit: int
    remaining: int
    reset_at: datetime
    scope: Literal["session", "ip"]
