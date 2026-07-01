from pydantic import BaseModel


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
