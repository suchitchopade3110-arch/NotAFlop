from agents.base_agent import AGENT_SYSTEM_SUFFIX, BaseAgent
from core.config import ANALYSIS_MODEL, REASONING_MODEL


class SpecialistAgent(BaseAgent):
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
            f"Rubric:\n{self.rubric}\n"
            f"{AGENT_SYSTEM_SUFFIX}"
        )


ALL_AGENTS = [
    SpecialistAgent(
        "problem",
        "Problem",
        "Reward painful, frequent, specific problems with an identifiable buyer. Penalize vague annoyances.",
        REASONING_MODEL,
    ),
    SpecialistAgent(
        "solution",
        "Solution",
        "Reward a crisp solution that directly resolves the stated pain and can be built into a focused MVP.",
        REASONING_MODEL,
    ),
    SpecialistAgent(
        "tam",
        "TAM",
        "Reward markets that are large enough, reachable, and supported by the supplied market signals.",
    ),
    SpecialistAgent(
        "team",
        "Team",
        "Reward founder-market fit, credible execution ability, and clear gaps that can be hired for.",
    ),
    SpecialistAgent(
        "moat",
        "Moat",
        "Reward distribution, data, workflow lock-in, network effects, or speed advantages that can compound.",
    ),
    SpecialistAgent(
        "unit_economics",
        "Unit Economics",
        "Reward plausible pricing, low acquisition friction, strong retention, and healthy gross margins.",
    ),
    SpecialistAgent(
        "gtm",
        "Go-to-Market",
        "Reward a specific initial customer segment and credible channels to reach them quickly.",
    ),
    SpecialistAgent(
        "risk",
        "Risk",
        "Reward ideas with manageable technical, regulatory, adoption, and competitive risks.",
        REASONING_MODEL,
    ),
    SpecialistAgent(
        "timing",
        "Timing",
        "Reward ideas riding urgent behavioral, regulatory, technology, or market shifts right now.",
    ),
    SpecialistAgent(
        "ask",
        "Ask",
        "Reward clear next asks: pilot, interview, waitlist, MVP scope, or funding milestone.",
    ),
    SpecialistAgent(
        "yc_signal",
        "YC Signal",
        "Reward ideas with YC-style traits: acute pain, fast iteration, simple wedge, and strong founder learning loops.",
        REASONING_MODEL,
    ),
]
