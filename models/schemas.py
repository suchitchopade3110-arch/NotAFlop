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