import json
from abc import ABC, abstractmethod
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
            f"Market signals:\n{json.dumps(state['signals'], indent=2)}"
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
