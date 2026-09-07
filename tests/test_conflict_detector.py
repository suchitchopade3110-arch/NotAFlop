"""B4 — rule-based cross-source conflict detection."""
from services.conflict_detector import detect_conflicts


def _ok(source, payload):
    return {"source": source, "status": "ok", "payload": payload, "fetched_at": "2026-01-01T00:00:00Z"}


def _unavailable(source):
    return {"source": source, "status": "unavailable", "payload": None, "fetched_at": "2026-01-01T00:00:00Z", "reason": "down"}


def test_no_conflicts_when_signals_empty():
    assert detect_conflicts({}) == []


def test_no_conflicts_when_sources_agree():
    signals = {
        "google_trends": _ok("google_trends", {"trend": "rising"}),
        "reddit": _ok("reddit", {"pain_frequency": "high"}),
    }
    assert detect_conflicts(signals) == []


def test_declining_trend_vs_high_pain_is_a_conflict():
    signals = {
        "google_trends": _ok("google_trends", {"trend": "declining"}),
        "reddit": _ok("reddit", {"pain_frequency": "high"}),
    }
    conflicts = detect_conflicts(signals)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["dimension"] == "interest_vs_pain"
    assert set(c["sources"]) == {"google_trends", "reddit"}
    assert c["directions"]["google_trends"] == "declining"
    assert c["directions"]["reddit"] == "high pain"
    assert c["description"]


def test_rising_trend_vs_low_pain_is_a_conflict():
    signals = {
        "google_trends": _ok("google_trends", {"trend": "rising"}),
        "hacker_news": _ok("hacker_news", {"founder_pain_signal": "low"}),
    }
    conflicts = detect_conflicts(signals)
    assert len(conflicts) == 1
    assert conflicts[0]["sources"] == ["google_trends", "hacker_news"]


def test_can_detect_conflicts_against_multiple_pain_sources():
    signals = {
        "google_trends": _ok("google_trends", {"trend": "declining"}),
        "reddit": _ok("reddit", {"pain_frequency": "high"}),
        "hacker_news": _ok("hacker_news", {"founder_pain_signal": "high"}),
    }
    conflicts = detect_conflicts(signals)
    dims_sources = {tuple(sorted(c["sources"])) for c in conflicts}
    assert ("google_trends", "reddit") in dims_sources
    assert ("google_trends", "hacker_news") in dims_sources


def test_saturated_market_vs_high_pain_is_a_conflict():
    signals = {
        "product_hunt": _ok("product_hunt", {"market_signal": "saturated"}),
        "reddit": _ok("reddit", {"pain_frequency": "high"}),
    }
    conflicts = detect_conflicts(signals)
    assert len(conflicts) == 1
    assert conflicts[0]["dimension"] == "market_saturation_vs_pain"


def test_unavailable_source_never_produces_a_conflict():
    """A missing/unavailable source must never be treated as implicitly
    agreeing or disagreeing — no conflict fabricated from absent data."""
    signals = {
        "google_trends": _ok("google_trends", {"trend": "declining"}),
        "reddit": _unavailable("reddit"),
    }
    assert detect_conflicts(signals) == []


def test_empty_source_never_produces_a_conflict():
    signals = {
        "google_trends": _ok("google_trends", {"trend": "declining"}),
        "reddit": {"source": "reddit", "status": "empty", "payload": {"post_count": 0}, "fetched_at": "2026-01-01T00:00:00Z"},
    }
    assert detect_conflicts(signals) == []


def test_legacy_flat_dict_signals_still_work():
    # "raw"/"post_count" present (non-empty) so B2's normalizer classifies
    # these as "ok" rather than "empty" — see services.data_sources.result.
    legacy_signals = {
        "google_trends": {"trend": "declining", "raw": [80, 60, 40]},
        "reddit": {"pain_frequency": "high", "post_count": 50},
    }
    conflicts = detect_conflicts(legacy_signals)
    assert len(conflicts) == 1
    assert conflicts[0]["dimension"] == "interest_vs_pain"


def test_no_llm_call_involved():
    """Pure rule-based detection — the module must not import the Groq
    client at all, confirming detect_conflicts can never make an LLM call."""
    from services import conflict_detector
    assert "groq_client" not in vars(conflict_detector)
    assert "chat" not in vars(conflict_detector)
