import json
from abc import ABC, abstractmethod
from core.config import ANALYSIS_MODEL
from services.groq_client import chat
from orchestrator.state import AgentOutput


class BaseAgent(ABC):
    name: str
    model: str
    max_tokens: int = 800
    pass_threshold: int = 6     # score >= 6 = passed

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    def build_user_message(self, state: dict) -> str:
        return (
            f"Founder pitch:\n\"\"\"\n{state['transcript']}\n\"\"\"\n\n"
            f"Market signals:\n{json.dumps(state['signals'], indent=2)}\n\n"
            "Note: If any market signal source has status 'unavailable', treat that source as missing/unverified data. Do not hallucinate or assume signal values for unavailable sources."
        )

    async def run(self, state: dict) -> AgentOutput:
        user_msg = self.build_user_message(state)
        raw = await chat(self.model, self.system_prompt, user_msg, self.max_tokens)

        try:
            data = json.loads(raw)
            score = int(data["score"])
            return AgentOutput(
                agent=self.name,
                passed=score >= self.pass_threshold,
                score=score,
                evidence=str(data.get("evidence", "")),
                feedback=str(data.get("feedback", "")),
            )
        except Exception:
            return AgentOutput(
                agent=self.name,
                passed=False,
                score=0,
                evidence="",
                feedback=f"{self.name} agent failed to parse response.",
            )


AGENT_SYSTEM_SUFFIX = """
Respond ONLY with valid JSON, no markdown, no explanation:
{"score": 0-10, "evidence": "one concrete data point", "feedback": "one-sentence verdict"}
"""


class SpecialistAgent(BaseAgent):
    """Generic rubric-driven agent — shared by every Phase 3 specialist
    that just needs a focus + rubric fed to build_user_message's transcript
    and signals. Lives here (not specialist_agents.py) so agent modules
    outside that one file (e.g. lovers_test.py) can construct instances
    without an import cycle back through the registry."""

    def __init__(self, name: str, focus: str, rubric: str, model: str = ANALYSIS_MODEL):
        self.name = name
        self.focus = focus
        self.rubric = rubric
        self.model = model

    @property
    def system_prompt(self) -> str:
        return (
            f"You are NotAFlop's {self.focus} specialist. "
            "Score this startup idea like a strict but useful VC analyst.\n\n"
            f"Dimension Focus: {self.focus}\n"
            f"Rubric:\n{self.rubric}\n\n"
            "Scoring Scale:\n"
            "- 0-3: unaddressed, absent, or contradicted.\n"
            "- 4-6: plausible or supported by general market signals, but lacking explicit concrete details or metrics in the transcript for this dimension.\n"
            "- 7-8: verified by ONE specific, explicit data point or metric directly relevant to this dimension.\n"
            "- 9-10: STRICT: requires MULTIPLE independent, explicit metrics or verified data points. Never award 9-10 based on a single data point or single signal alone.\n\n"
            "Rules:\n"
            f"1. Primary Source: The founder transcript is a primary source of evidence. Evaluate facts stated directly in the transcript first (e.g. buyer, defect metrics, team background), alongside market signals. Do not ignore clear transcript details or prefer generic market signals over concrete facts in the pitch.\n"
            f"2. Specificity Guard: General market signals (e.g. Reddit counts) indicate macro background interest, but CANNOT substitute for a vague or absent mechanism in the transcript. If the transcript states only a broad/vague annoyance without a specific buyer or concrete wedge, score no higher than 4.\n"
            f"3. Missing Information Penalty: If no information relevant to {self.focus} is present in either the pitch or signals, score no higher than 3 and state 'No relevant information in pitch or signals' in evidence.\n"
            f"4. Evidence Focus: The evidence field MUST cite a data point specifically relevant to {self.focus}. Do not cite metrics belonging to other dimensions.\n\n"
            "Respond ONLY with valid JSON, no markdown, no explanation:\n"
            '{"score": 0-10, "evidence": "one data point specifically relevant to ' + self.focus + ' (or state no relevant info)", "feedback": "one-sentence verdict"}'
        )
