"""
Phase 4 - Gate.
Single source of truth for VC-weighted scoring, verdict, and gate reasoning.
Consumed by Phase 3's orchestrator (for the inline SSE 'final' event) and by
the standalone Phase 4 /gate endpoint (for a clean, re-computable verdict).
"""
from orchestrator.state import AgentOutput

WEIGHTS: dict[str, float] = {
    "problem": 1.20,
    "solution": 1.10,
    "tam": 1.00,
    "team": 0.90,
    "moat": 0.90,
    "unit_economics": 0.85,
    "gtm": 0.85,
    "risk": 0.95,
    "timing": 0.95,
    "ask": 0.80,
    "yc_signal": 1.00,
}

GO_THRESHOLD = 70
PIVOT_THRESHOLD = 50


def aggregate_results(results: dict[str, AgentOutput]) -> tuple[int, str]:
    """Weighted score (0-100) + verdict. Pure function, no I/O."""
    weighted_sum = 0.0
    weight_total = 0.0

    for name, weight in WEIGHTS.items():
        if name in results:
            weighted_sum += results[name]["score"] * weight
            weight_total += weight

    raw_score = (weighted_sum / weight_total) * 10 if weight_total > 0 else 0
    final_score = round(min(100, max(0, raw_score)))
    verdict = _verdict_for(final_score)

    return final_score, verdict


def _verdict_for(score: int) -> str:
    if score >= GO_THRESHOLD:
        return "go"
    elif score >= PIVOT_THRESHOLD:
        return "pivot"
    return "no-go"


def top_risks(results: dict[str, AgentOutput], n: int = 3) -> list[dict]:
    """Lowest-scoring agents, weighted-priority order (biggest weighted drag first)."""
    scored = [
        {
            "agent": name,
            "score": out["score"],
            "weight": WEIGHTS.get(name, 1.0),
            "feedback": out["feedback"],
        }
        for name, out in results.items()
        if name in WEIGHTS
    ]
    # Biggest weighted drag = (10 - score) * weight, descending
    scored.sort(key=lambda r: (10 - r["score"]) * r["weight"], reverse=True)
    return [{"agent": r["agent"], "score": r["score"], "feedback": r["feedback"]} for r in scored[:n]]


def gate_reason(results: dict[str, AgentOutput], score: int, verdict: str) -> str:
    """One sentence citing the agents that drove the verdict."""
    if not results:
        return "No agent results available."

    scored = [(name, out["score"], WEIGHTS.get(name, 1.0)) for name, out in results.items() if name in WEIGHTS]

    if verdict == "go":
        best = sorted(scored, key=lambda r: r[1] * r[2], reverse=True)[:2]
        names = " and ".join(f"{n.replace('_', ' ').title()} ({s}/10)" for n, s, _ in best)
        return f"Cleared the gate on strong {names}."
    else:
        worst = sorted(scored, key=lambda r: (10 - r[1]) * r[2], reverse=True)[:2]
        names = " and ".join(f"{n.replace('_', ' ').title()} ({s}/10)" for n, s, _ in worst)
        verb = "Blocked" if verdict == "no-go" else "Held to Pivot"
        return f"{verb} primarily by weak {names}."


def compute_gate(results: dict[str, AgentOutput]) -> dict:
    """Full Phase 4 output: score, verdict, top risks, gate reason."""
    score, verdict = aggregate_results(results)
    return {
        "score": score,
        "verdict": verdict,
        "top_risks": top_risks(results),
        "gate_reason": gate_reason(results, score, verdict),
    }
