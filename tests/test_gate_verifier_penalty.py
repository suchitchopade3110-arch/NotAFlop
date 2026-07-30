from models.documents import VerifierOutput
from services.gate import GO_THRESHOLD, apply_verifier_penalty


def _verifier(confidence: int) -> VerifierOutput:
    return VerifierOutput(confidence_score=confidence, passed=confidence >= 6, evidence="e", feedback="f", model="m")


def test_full_confidence_leaves_score_unchanged():
    adjusted, verdict, flipped = apply_verifier_penalty(80, _verifier(10))
    assert adjusted == 80
    assert flipped is False


def test_zero_confidence_applies_heaviest_penalty():
    adjusted, verdict, flipped = apply_verifier_penalty(100, _verifier(0))
    assert adjusted == 70  # multiplier 0.7


def test_mid_confidence_applies_partial_penalty():
    adjusted, verdict, flipped = apply_verifier_penalty(100, _verifier(5))
    assert adjusted == 85  # multiplier 0.7 + 0.03*5 = 0.85


def test_verdict_flip_detected_when_penalty_crosses_go_threshold():
    raw_score = GO_THRESHOLD + 1  # 71 — a "go" on raw
    adjusted, verdict, flipped = apply_verifier_penalty(raw_score, _verifier(0))  # multiplier 0.7
    assert adjusted < GO_THRESHOLD
    assert verdict != "go"
    assert flipped is True


def test_no_flip_when_verdict_unaffected():
    adjusted, verdict, flipped = apply_verifier_penalty(20, _verifier(0))  # already deep in no-go
    assert verdict == "no-go"
    assert flipped is False


def test_adjusted_score_bounded_0_to_100():
    adjusted, _, _ = apply_verifier_penalty(0, _verifier(10))
    assert adjusted == 0
