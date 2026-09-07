from services import share


def test_top_reasons_go_picks_strongest():
    scores = {"problem": 9, "solution": 8, "timing": 3}
    reasons = share.top_reasons(scores, "go", n=2)
    assert len(reasons) == 2
    assert "Strong" in reasons[0]
    assert "Problem" in reasons[0] or "Solution" in reasons[0]


def test_top_reasons_no_go_picks_weakest():
    scores = {"problem": 9, "solution": 2, "timing": 1}
    reasons = share.top_reasons(scores, "no-go", n=2)
    assert all("Weak" in r for r in reasons)
    joined = " ".join(reasons)
    assert "Timing" in joined or "Solution" in joined


def test_top_reasons_ignores_non_gate_dimensions():
    scores = {"not_a_real_dimension": 10, "problem": 5}
    reasons = share.top_reasons(scores, "go")
    assert all("not_a_real_dimension" not in r.lower().replace(" ", "_") for r in reasons)


def test_top_reasons_empty_scores():
    assert share.top_reasons({}, "go") == []
