from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

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


# ── Plan & Build (Phase 5) ───────────────────────────────────
class RolePriority(str, Enum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    NICE_TO_HAVE = "nice_to_have"


class RoadmapMilestone(BaseModel):
    day_range: str = Field(..., description="e.g. 'Day 1-30'")
    block_title: str = Field(..., description="e.g. 'MVP Build'")
    tasks: list[str]
    deliverable: str
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Top risks from Phase 4 that this block should actively address",
    )


class TeamRole(BaseModel):
    role: str
    priority: RolePriority
    reason: str = Field(..., description="Why this role matters for THIS idea specifically")
    skills: list[str]
    where_to_find: list[str] = Field(
        default_factory=lambda: ["YC Co-founder Match", "AngelList", "Wellfound", "LinkedIn"]
    )


class PlanRequest(BaseModel):
    report_id: str = Field(..., description="Public ID of the persisted report (e.g. 'rep_...')")
    idea_summary: str | None = Field(
        None, description="Optional override for idea summary. Defaults to report transcript."
    )
    vertical: str | None = Field(
        None, description="Optional vertical tag: 'marketplace', 'fintech', 'devtool', 'consumer_social'"
    )


class PlanResponse(BaseModel):
    roadmap: list[RoadmapMilestone]
    team: list[TeamRole]
    revenue_model_options: list[str]
    solo_founder_note: str | None = Field(
        None, description="Populated only when idea can realistically be solo-built past MVP"
    )
