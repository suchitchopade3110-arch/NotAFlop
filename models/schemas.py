import re
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.validation import TranscriptValidationError, validate_transcript
from models.documents import AgentResultRecord, VerifierOutput

# Deliberately not pydantic's EmailStr (which pulls in the email-validator
# dependency) — a permissive shape check is all a magic-link destination
# needs; deliverability is proven by the founder actually clicking the
# link, not by this regex.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Transcribe ────────────────────────────────────────────────
class TranscribeResponse(BaseModel):
    transcript: str


# ── Filter ────────────────────────────────────────────────────
class FilterRequest(BaseModel):
    transcript: str

    @field_validator("transcript")
    @classmethod
    def _validate_transcript(cls, value: str) -> str:
        # C5: shared across every transcript entry path — see
        # core/validation.py's module docstring.
        try:
            return validate_transcript(value)
        except TranscriptValidationError as exc:
            raise ValueError(exc.detail) from exc


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

    signal_quality: float = 0.0
    signal_quality_by_source: dict[str, float] = Field(default_factory=dict)
    low_confidence: bool = False
    conflicts: list[dict] = Field(default_factory=list)
    report_cost_usd: float = 0.0

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


class VerifierDivergenceStats(BaseModel):
    """GET /internal/verifier/stats — shadow-mode divergence between
    raw_score and adjusted_score across stored report snapshots that
    carry a Verifier result. Read-only observability, no gating."""

    count: int
    mean_absolute_delta: float
    max_delta: int
    distribution: dict[str, int]


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


# ── Phase 2: progressive identity (A4) ───────────────────────────────
class SessionResponse(BaseModel):
    session_id: str


class ClaimRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        candidate = value.strip().lower()
        if not _EMAIL_RE.match(candidate):
            raise ValueError("Not a valid email address.")
        return candidate


class ClaimResponse(BaseModel):
    status: Literal["sent"]


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    account_id: str
    email: str
    session_id: str
    claimed_ideas: int


class MeResponse(BaseModel):
    session_id: str
    account_id: str | None
    email: str | None
    plan: str | None
    owned_idea_count: int
    report_count: int


# ── Phase 2: the log surface (B1/B2) ─────────────────────────────────
class IdeaSummary(BaseModel):
    """One row of GET /v1/ideas."""

    idea_id: str
    keyword: str
    raw_score: int | None
    verdict: str | None
    status: str
    last_snapshot_at: datetime | None
    created_at: datetime


class IdeaDetailResponse(BaseModel):
    idea_id: str
    raw_text: str
    keyword: str
    status: str
    share_token: str
    current_snapshot_id: str | None
    weights_version: int | None
    raw_score: int | None
    verdict: str | None
    created_at: datetime
    updated_at: datetime


class SnapshotSummary(BaseModel):
    snapshot_id: str
    trigger: str
    raw_score: int
    verdict: str
    weights_version: int
    deltas: dict
    version_crossing: bool
    cost: float
    created_at: datetime


class ShareCardResponse(BaseModel):
    """GET /v1/share/{token} — public, no auth. Verdict/score/headline
    reasons only, never raw pitch text, email, or evidence payloads."""

    verdict: str
    raw_score: int
    keyword: str
    top_reasons: list[str]
    created_at: datetime


class TimelineEntry(BaseModel):
    """One row of GET /v1/ideas/{id}/timeline — a merged, chronological
    feed of every event type."""

    type: Literal["snapshot", "evidence", "milestone", "criterion"]
    at: datetime
    payload: dict


# ── Phase 2: kill-criteria (C3) ───────────────────────────────────────
class CriterionRequest(BaseModel):
    statement: str
    metric: str
    threshold: str
    deadline: datetime

    @field_validator("statement", "metric", "threshold")
    @classmethod
    def _reject_vague(cls, value: str) -> str:
        # A commitment that cannot fail is not a commitment — reject
        # empty/near-empty statements at the API boundary rather than
        # accepting an unfalsifiable criterion.
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Too vague to be a falsifiable commitment.")
        return cleaned

    @field_validator("deadline")
    @classmethod
    def _deadline_in_future(cls, value: datetime) -> datetime:
        from datetime import timezone

        deadline = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if deadline <= datetime.now(timezone.utc):
            raise ValueError("Deadline must be in the future.")
        return deadline


class CriterionResponse(BaseModel):
    criterion_id: str
    idea_id: str
    statement: str
    metric: str
    threshold: str
    deadline: datetime
    status: str
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime


class ResolveCriterionRequest(BaseModel):
    outcome: Literal["met", "failed"]
    note: str

    @field_validator("note")
    @classmethod
    def _note_required(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("A resolution needs a note explaining what happened.")
        return cleaned


# ── Phase 2: evidence and milestones (C4) ────────────────────────────
class EvidenceRequest(BaseModel):
    type: Literal["interview", "waitlist", "revenue", "letter_of_intent", "other"]
    payload: dict = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _payload_not_empty(cls, value: dict) -> dict:
        if not value:
            raise ValueError("Evidence payload is empty.")
        return value


class EvidenceResponse(BaseModel):
    evidence_id: str
    idea_id: str
    type: str
    payload: dict
    submitted_at: datetime
    triggered_snapshot_id: str | None
    snapshot: SnapshotSummary | None = None


class MilestoneResponse(BaseModel):
    milestone_id: str
    day_range: str
    block_title: str
    tasks: list[str]
    deliverable: str
    completed: bool
    completed_at: datetime | None
    evidence_id: str | None


class MilestonePatchRequest(BaseModel):
    completed: bool
    evidence_id: str | None = None


# ── Phase 2: internal re-scoring (C7) ────────────────────────────────
class RescoreRequest(BaseModel):
    idea_id: str | None = Field(None, description="Re-score a single idea. Omit to sweep every idea.")


class RescoreResult(BaseModel):
    idea_id: str
    snapshot_id: str | None
    status: Literal["rescored", "skipped_no_change", "failed"]


class RescoreResponse(BaseModel):
    weights_version: int
    results: list[RescoreResult]
