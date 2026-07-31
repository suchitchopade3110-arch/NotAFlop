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
    ip: str | None = None

    idea_hash: str
    transcript: str
    keyword: str
    signals: dict = Field(default_factory=dict)
    filter_result: dict | None = None

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
