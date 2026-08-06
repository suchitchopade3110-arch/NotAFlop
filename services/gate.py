"""
Phase 4 - Gate.
Single source of truth for VC-weighted scoring, verdict, and gate reasoning.
Consumed by Phase 3's orchestrator (for the inline SSE 'final' event) and by
the standalone Phase 4 /gate endpoint (for a clean, re-computable verdict).

WEIGHTS_VERSION lives here, next to the WEIGHTS it versions, and is stamped
onto every persisted report at write time (never inferred at read) — bump
it any time a weight changes, an agent is added/removed, or the aggregation
arithmetic itself changes.

Weighting arithmetic, spelled out because additive and renormalized are NOT
numerically equivalent for a given weight value:

  aggregate_results() computes weighted_sum / weight_total, where
  weight_total is the dynamic sum of the weights of whichever agents are
  PRESENT in a given call. That dynamic denominator does two distinct jobs
  that are easy to conflate:

  1. Missing-agent tolerance (orthogonal to versioning, always been true):
     if an agent errored out and is absent from `results`, its weight
     drops out of both the numerator and the denominator, so the average
     is computed over whoever's actually present instead of being dragged
     down by phantom zeros. This has nothing to do with lovers_test.

  2. How lovers_test (added at WEIGHTS_VERSION 2) was folded in: it was
     APPENDED to WEIGHTS at 0.85, not carved out of the original 10
     weights' fixed budget. The other 10 weights are byte-for-byte
     unchanged from v1 (they still sum to 10.50 on their own) — adding
     lovers_test only grows weight_total when it's present, which dilutes
     everyone else's *share* of the final score without rescaling anyone's
     individual weight. That's additive, confirmed against the actual
     arithmetic: 11 agents at 8/10 with lovers_test absent scores 80;
     the same 11 plus lovers_test at 2/10 scores 76 (weighted_sum=85.7,
     weight_total=11.35, 85.7/11.35*10=75.5..., rounds to 76). A true
     renormalization — rescaling the original 10 weights so lovers_test
     carves a slice out of a fixed 10.50 budget instead of growing it —
     would score 75 for that same example instead. 76 is what the code
     produces; see tests/test_gate.py for the pinned worked example.

  Reports persist each agent's raw score specifically so they can be
  re-aggregated under a different WEIGHTS_VERSION retroactively; scores
  computed under different WEIGHTS_VERSIONs aren't directly comparable.
"""
import logging

from models.documents import VerifierOutput
from orchestrator.state import AgentOutput

logger = logging.getLogger("notaflop.gate")

WEIGHTS_VERSION = 2  # bump on any change to WEIGHTS below, or to the aggregation arithmetic itself

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
    "lovers_test": 0.85,  # added in WEIGHTS_VERSION 2 — additive, not renormalized (see module docstring)
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


def apply_verifier_penalty(raw_score: int, verifier: VerifierOutput) -> tuple[int, str, bool]:
    """
    Confidence multiplier, not another additive weight: the Verifier
    doesn't score a pitch dimension, it audits the other 12 agents, so a
    bad confidence_score should drag the WHOLE gate down rather than just
    losing its own slice of a weighted average.

    confidence_score=10 -> multiplier 1.0 (no change).
    confidence_score=0  -> multiplier 0.7 (heaviest penalty, 30% off).

    Returns (adjusted_score, adjusted_verdict, verdict_would_flip) — the
    last compares the verdict under raw_score against the verdict under
    adjusted_score. Shadow mode (VERIFIER_PENALTY_ENABLED=false) gates on
    raw_score regardless of this result; it's persisted/logged for
    calibration.
    """
    multiplier = 0.7 + 0.03 * verifier.confidence_score
    adjusted_score = round(min(100, max(0, raw_score * multiplier)))
    adjusted_verdict = _verdict_for(adjusted_score)
    raw_verdict = _verdict_for(raw_score)
    verdict_would_flip = adjusted_verdict != raw_verdict

    if verdict_would_flip:
        logger.warning(
            "verifier_verdict_flip raw_score=%d raw_verdict=%s adjusted_score=%d "
            "adjusted_verdict=%s confidence_score=%d conflicts=%d",
            raw_score, raw_verdict, adjusted_score, adjusted_verdict,
            verifier.confidence_score, len(verifier.conflicts),
        )

    return adjusted_score, adjusted_verdict, verdict_would_flip


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
