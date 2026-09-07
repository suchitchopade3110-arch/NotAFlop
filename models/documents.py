"""
Pydantic v2 models for MongoDB documents. No raw dicts cross the
repository boundary — routers and orchestrator code build these, and
repositories serialize/deserialize them.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentResultRecord(BaseModel):
    """One specialist agent's output, as persisted on a report."""

    agent: str
    passed: bool
    score: int
    evidence: str
    feedback: str
    model: str


class VerifierOutput(BaseModel):
    """
    The Verifier meta-agent's output. Deliberately NOT an AgentOutput —
    it doesn't score a pitch dimension, it audits the other 10 agents'
    outputs for contradictions and unsupported claims. Lives in its own
    GraphState slot and its own field on the report doc, never inside
    results/agent_results.
    """

    agent: Literal["verifier"] = "verifier"
    confidence_score: int  # 0-10, per the Verifier rubric (10 = fully consistent)
    passed: bool
    conflicts: list[str] = Field(default_factory=list)
    evidence: str
    feedback: str
    model: str


class ReportDocument(BaseModel):
    public_id: str
    session_id: str
    account_id: str | None = None  # nullable, unused until Stage C's account/auth work lands
    ip: str | None = None

    idea_hash: str
    transcript: str
    keyword: str
    signals: dict = Field(default_factory=dict)
    filter_result: dict | None = None

    # B3: disclosure layer over `signals` — never feeds back into scoring.
    signal_quality: float = 0.0
    signal_quality_by_source: dict[str, float] = Field(default_factory=dict)
    low_confidence: bool = False

    # B4: rule-based cross-source conflicts detected on `signals`. Each
    # entry: {dimension, sources, directions, description}. Also a
    # disclosure layer — never feeds back into scoring.
    conflicts: list[dict] = Field(default_factory=list)

    # C3: aggregate Groq cost across every agent call for this report (see
    # services/cost_tracking.py). Approximate/observability, not billing-
    # grade — never fed back into scoring.
    report_cost_usd: float = 0.0

    agent_results: dict[str, AgentResultRecord] = Field(default_factory=dict)
    verifier: VerifierOutput | None = None

    weights_version: int
    raw_score: int
    adjusted_score: int | None = None
    verdict: str  # derived from raw_score while VERIFIER_PENALTY_ENABLED is false
    gating_score: Literal["raw", "adjusted"] = "raw"
    verdict_would_flip: bool = False
    tier_reached: int = 1

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SessionDocument(BaseModel):
    session_id: str
    account_id: str | None = None  # nullable, unused until Stage C's account/auth work lands
    ip: str | None = None
    report_count: int = 0

    created_at: datetime = Field(default_factory=_utcnow)
    last_seen_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime  # TTL index target — set by the repository


class FeedbackDocument(BaseModel):
    """Schema only — no repository or endpoints yet. Phase 6."""

    public_id: str
    session_id: str
    rating: int
    comment: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


# ── Phase 2: the evidence log ────────────────────────────────────────
#
# Five collections (accounts, ideas, snapshots, criteria, evidence),
# additive to the v1 reports/sessions above — see A1's audit for how they
# relate: `reports` stays the untouched v1 pipeline artifact; an `idea` is
# created by *promoting* a completed report (POST /v1/ideas), and every
# score written after that point is a `snapshot`, owned exclusively by
# services/log_service.py (constraint #6 — no other module writes here).
#
# `milestones` is not a 6th top-level collection (the task's schema table
# lists exactly five) — it's embedded on IdeaDocument as MilestoneRecord,
# each carrying its own id for PATCH /v1/milestones/{mid}.


class AccountDocument(BaseModel):
    account_id: str
    email: str
    created_at: datetime = Field(default_factory=_utcnow)
    plan: Literal["free", "pro"] = "free"
    session_ids: list[str] = Field(default_factory=list)


class MilestoneRecord(BaseModel):
    """One roadmap block, with completion state — embedded on
    IdeaDocument rather than its own collection (see module docstring)."""

    milestone_id: str
    day_range: str
    block_title: str
    tasks: list[str] = Field(default_factory=list)
    deliverable: str
    completed: bool = False
    completed_at: datetime | None = None
    evidence_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class IdeaDocument(BaseModel):
    """A durable, re-runnable idea log. `idea_hash` is an index only —
    never a cache short-circuit (see repositories/idea_repository.py):
    two founders pitching the same idea_hash each get their own
    IdeaDocument and independent score history."""

    idea_id: str
    session_id: str
    account_id: str | None = None
    idea_hash: str
    raw_text: str
    normalized_text: str
    keyword: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    current_snapshot_id: str | None = None
    share_token: str
    status: Literal["active", "archived", "deleted"] = "active"
    # The v1 report this idea was promoted from (POST /v1/ideas) — kept
    # for traceability only; the idea's own snapshot history is what
    # everything past promotion reads from, never this report again.
    source_report_id: str | None = None
    milestones: list[MilestoneRecord] = Field(default_factory=list)
    # C1 idempotency: a short-TTL lock so a scheduler tick and a manual
    # force-re-run (or two overlapping sweeps) can't both run a re-score
    # for the same idea at once. None/expired = free to acquire.
    scheduler_lock_until: datetime | None = None


class SnapshotDocument(BaseModel):
    """One point-in-time score. Immutable once written — a re-score never
    edits a prior snapshot (see C7); it only ever appends a new one.
    `raw_score` gates (tier/verdict logic); `adjusted_score` is carried
    for parity with ReportDocument but Phase 2 re-runs don't invoke the
    Verifier (out of the reduced re-run sets in C1), so it mirrors
    raw_score unless a future phase changes that."""

    snapshot_id: str
    idea_id: str
    agent_scores: dict[str, int] = Field(default_factory=dict)
    raw_score: int
    adjusted_score: int | None = None
    verdict: str
    weights_version: int
    sources: list[str] = Field(default_factory=list)
    # The actual market-signals payload as of this snapshot (beyond the
    # table's minimum fields, additive) — an evidence-gated re-run (C4)
    # never refreshes the data layer, so it needs the previous snapshot's
    # signals to feed the agents it does re-run; storing them here keeps
    # that "carried forward, not re-derived on read" for signals too.
    signals: dict = Field(default_factory=dict)
    signal_quality: float = 0.0
    conflicts: list[dict] = Field(default_factory=list)
    trigger: Literal["initial", "scheduled", "evidence", "manual"] = "initial"
    # Per-dimension + aggregate deltas against the previous snapshot,
    # computed and stored at write time (C2) — never derived on read.
    # Empty on the first (`initial`) snapshot, which has no predecessor.
    deltas: dict = Field(default_factory=dict)
    # True when this snapshot's weights_version differs from the
    # snapshot it was diffed against — the delta is real but not a
    # like-for-like movement, and callers must not present it as one.
    version_crossing: bool = False
    cost: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)


class CriterionDocument(BaseModel):
    """A falsifiable kill-criterion the founder commits to at validation
    time. `metric` + `threshold` + `deadline` are all required at the API
    boundary (routers/phase2_criteria.py) — a commitment with no way to
    fail isn't a commitment."""

    criterion_id: str
    idea_id: str
    statement: str
    metric: str
    threshold: str
    deadline: datetime
    status: Literal["pending", "met", "failed", "lapsed"] = "pending"
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    # C6: set once a deadline-approaching reminder has been sent, so the
    # sweep never re-notifies the same criterion every tick.
    reminder_sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class EvidenceDocument(BaseModel):
    """Founder-submitted proof against the pitch — interviews, waitlist
    numbers, revenue, letters of intent, or a kill-criterion's recorded
    outcome. `triggered_snapshot_id` links back to the evidence-gated
    snapshot this submission produced, once that re-score completes."""

    evidence_id: str
    idea_id: str
    type: Literal[
        "interview", "waitlist", "revenue", "letter_of_intent", "criterion_resolution", "other"
    ]
    payload: dict = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=_utcnow)
    triggered_snapshot_id: str | None = None
