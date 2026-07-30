"""
Verifier — a meta-agent that cross-checks the other 12 specialists'
outputs for the same pitch, rather than scoring the pitch itself.

Deliberately NOT a BaseAgent/SpecialistAgent subclass: its input is the
other agents' completed AgentOutputs (not the raw transcript/signals),
and its output is VerifierOutput (models/documents.py) — a different
shape from AgentOutput on purpose, kept out of the shared
`results: dict[str, AgentOutput]` contract entirely (see GraphState /
orchestrator.graph).

Runs after all 12 specialists finish, since it needs their outputs —
a second "wave" in the fan-out, not part of the same asyncio.gather.
"""
import json

from core.config import REASONING_MODEL
from models.documents import VerifierOutput
from orchestrator.state import AgentOutput
from services.groq_client import chat

MODEL = REASONING_MODEL
MAX_TOKENS = 800

SYSTEM_PROMPT = """You are NotAFlop's Verifier. You do not score the startup pitch \
yourself — you audit the 12 specialist agents who already scored it, looking for \
contradictions between them and claims whose cited evidence doesn't actually support \
what's claimed.

Rubric (confidence_score, 0-10):
- 10 = no contradictions between any agents, and every claim is traceable to a \
concrete evidence snippet that actually supports it.
- 0 = agents directly contradict each other (e.g. one calls the market huge, another \
says there's no real market), or an agent cites evidence that does not support the \
claim it's attached to.
- Score between these extremes based on how many and how severe the contradictions \
or unsupported claims are.

Respond ONLY with valid JSON, no markdown, no explanation:
{"confidence_score": 0-10, "conflicts": ["one sentence per conflict found"], "evidence": "the clearest example", "feedback": "one-sentence verdict"}
"""

PASS_THRESHOLD = 6


def _build_user_message(results: dict[str, AgentOutput]) -> str:
    summarized = {
        name: {"score": out["score"], "evidence": out["evidence"], "feedback": out["feedback"]}
        for name, out in results.items()
    }
    return (
        "Cross-check these specialist agent outputs, all evaluating the same startup "
        "pitch. Flag direct contradictions between agents and any claim whose cited "
        "evidence doesn't actually support it.\n\n"
        f"Agent outputs:\n{json.dumps(summarized, indent=2)}"
    )


async def run(results: dict[str, AgentOutput]) -> VerifierOutput:
    user_msg = _build_user_message(results)
    raw = await chat(MODEL, SYSTEM_PROMPT, user_msg, MAX_TOKENS)

    try:
        data = json.loads(raw)
        confidence_score = int(data["confidence_score"])
        return VerifierOutput(
            confidence_score=confidence_score,
            passed=confidence_score >= PASS_THRESHOLD,
            conflicts=[str(c) for c in data.get("conflicts", [])],
            evidence=str(data.get("evidence", "")),
            feedback=str(data.get("feedback", "")),
            model=MODEL,
        )
    except Exception:
        return VerifierOutput(
            confidence_score=0,
            passed=False,
            conflicts=[],
            evidence="",
            feedback="Verifier failed to parse response.",
            model=MODEL,
        )
