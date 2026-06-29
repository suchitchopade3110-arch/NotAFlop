from typing import TypedDict, Any


class AgentOutput(TypedDict):
    agent: str
    passed: bool
    score: int          # 0-10
    evidence: str       # one concrete evidence snippet
    feedback: str       # one-sentence verdict


class GraphState(TypedDict):
    # Inputs
    transcript: str
    keyword: str
    signals: dict       # from Smart Data Layer

    # Agent outputs — populated as each agent completes
    results: dict[str, AgentOutput]

    # Final
    aggregated_score: int | None
    verdict: str | None         # "go" | "no-go" | "pivot"
    errors: list[str]
