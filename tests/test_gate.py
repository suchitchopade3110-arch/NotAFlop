from core.config import WEIGHTS_VERSION
from orchestrator.state import AgentOutput
from services.gate import WEIGHTS, aggregate_results


def _output(name: str, score: int) -> AgentOutput:
    return AgentOutput(agent=name, passed=score >= 6, score=score, evidence="e", feedback="f")


def test_lovers_test_is_in_weights():
    assert "lovers_test" in WEIGHTS
    assert WEIGHTS["lovers_test"] == 0.85


def test_weights_version_bumped():
    assert WEIGHTS_VERSION == 2


def test_lovers_test_weight_is_additive_not_renormalized():
    """The other 10 core weights are untouched — appending lovers_test
    grows the total rather than carving a slice out of a fixed budget."""
    others_total = sum(w for name, w in WEIGHTS.items() if name != "lovers_test")
    assert abs(others_total - 10.50) < 1e-9


def test_lovers_test_low_score_measurably_dilutes_aggregate():
    """Worked example matching the approved algebra: 11 original agents
    at 8/10 with lovers_test absent scores 80. Adding a lovers_test
    result of 2/10 (weight 0.85) pulls it down via the growing
    denominator — not just a small slice, a dilution of everyone."""
    baseline_results = {
        name: _output(name, 8) for name in WEIGHTS if name != "lovers_test"
    }
    baseline_score, _ = aggregate_results(baseline_results)
    assert baseline_score == 80

    with_lovers_test = dict(baseline_results)
    with_lovers_test["lovers_test"] = _output("lovers_test", 2)
    diluted_score, _ = aggregate_results(with_lovers_test)

    assert diluted_score < baseline_score
    assert diluted_score == 76  # 85.7 / 11.35 * 10 = 75.5..., rounds to 76


def test_aggregate_results_empty_returns_zero_and_no_go():
    score, verdict = aggregate_results({})
    assert score == 0
    assert verdict == "no-go"


def test_aggregate_results_missing_agents_still_computes():
    """A partial results dict (e.g. some agents errored) still produces a
    valid weighted average over whichever agents are present."""
    partial = {"problem": _output("problem", 10), "solution": _output("solution", 10)}
    score, verdict = aggregate_results(partial)
    assert score == 100
    assert verdict == "go"
