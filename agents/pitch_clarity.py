import json
from services.groq_client import chat
from models.schemas import AgentResult
from core.config import FILTER_MODEL, FILTER_MAX_TOKENS

SYSTEM = """You are a startup pitch clarity judge. Your job is to check if the founder's pitch can be understood by a stranger in 30 seconds.

Evaluate on this rubric:
- 8-10: Clear what it is, who it's for, and why it matters — no jargon
- 5-7: Mostly clear but missing one of the three elements
- 1-4: Confusing, jargon-heavy, or requires prior context to understand

Respond ONLY with valid JSON, no markdown, no explanation:
{"passed": true/false, "score": 0-10, "feedback": "one sentence"}

passed = true if score >= 6."""

async def run(transcript: str) -> AgentResult:
    user_msg = f'Founder pitch:\n"""\n{transcript}\n"""'
    raw = await chat(FILTER_MODEL, SYSTEM, user_msg, FILTER_MAX_TOKENS)

    try:
        data = json.loads(raw)
        return AgentResult(
            passed=bool(data["passed"]),
            score=int(data["score"]),
            feedback=str(data["feedback"]),
        )
    except Exception:
        return AgentResult(passed=False, score=0, feedback="Could not evaluate pitch clarity.")