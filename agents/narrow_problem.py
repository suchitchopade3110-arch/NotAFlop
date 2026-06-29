import json
from services.groq_client import chat
from models.schemas import AgentResult
from core.config import FILTER_MODEL, FILTER_MAX_TOKENS

SYSTEM = """You are a startup idea filter. Your job is to check if the founder's pitch describes ONE specific, narrow problem — not a broad vision or a solution.

Evaluate on this rubric:
- 8-10: Single, concrete pain point with a clear sufferer (e.g. "freelance designers spend 3 hours invoicing per client")
- 5-7: Somewhat specific but missing who suffers or how often
- 1-4: Too broad, vague, or describes a solution instead of a problem

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
        # Fallback if LLM returns malformed JSON
        return AgentResult(passed=False, score=0, feedback="Could not evaluate problem specificity.")