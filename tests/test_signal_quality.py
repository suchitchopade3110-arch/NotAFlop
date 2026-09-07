"""B3 — per-source and per-report signal_quality, and low_confidence."""
from services.data_sources.result import SignalResult, SignalStatus
from services.signal_quality import compute_report_signal_quality, compute_source_quality


def _result(source, status, payload=None):
    return SignalResult(source=source, status=SignalStatus(status), payload=payload)


def test_unavailable_rate_limited_error_score_zero():
    for status in ("unavailable", "rate_limited", "error"):
        assert compute_source_quality(_result("reddit", status)) == 0.0


def test_empty_scores_partial_credit():
    quality = compute_source_quality(_result("hacker_news", "empty", {"hit_count": 0, "sample_posts": []}))
    assert 0 < quality < 0.7


def test_ok_with_no_records_scores_base():
    quality = compute_source_quality(_result("reddit", "ok", {"post_count": 0, "sample_posts": []}))
    assert quality == 0.7


def test_ok_with_many_records_scores_higher():
    low = compute_source_quality(_result("reddit", "ok", {"post_count": 5, "sample_posts": []}))
    high = compute_source_quality(_result("reddit", "ok", {"post_count": 150, "sample_posts": []}))
    assert high > low
    assert high <= 1.0


def test_cached_result_scores_slightly_lower_than_fresh():
    fresh = compute_source_quality(_result("reddit", "ok", {"post_count": 50}))
    cached = compute_source_quality(_result("reddit", "ok", {"post_count": 50, "_cached": True}))
    assert cached < fresh


def test_report_quality_empty_signals_dict():
    quality, low_confidence, per_source = compute_report_signal_quality({})
    assert quality == 0.0
    assert low_confidence is True
    assert per_source == {}


def test_report_quality_averages_per_source():
    signals = {
        "reddit": {"source": "reddit", "status": "ok", "payload": {"post_count": 50}, "fetched_at": "2026-01-01T00:00:00Z"},
        "hacker_news": {"source": "hacker_news", "status": "unavailable", "payload": None, "fetched_at": "2026-01-01T00:00:00Z", "reason": "down"},
    }
    quality, low_confidence, per_source = compute_report_signal_quality(signals)
    assert per_source["reddit"] > 0
    assert per_source["hacker_news"] == 0.0
    assert quality == round((per_source["reddit"] + 0.0) / 2, 3)


def test_low_confidence_when_fewer_than_two_live_sources():
    one_live = {
        "reddit": {"source": "reddit", "status": "ok", "payload": {"post_count": 50}, "fetched_at": "2026-01-01T00:00:00Z"},
        "hacker_news": {"source": "hacker_news", "status": "unavailable", "payload": None, "fetched_at": "2026-01-01T00:00:00Z", "reason": "down"},
    }
    _, low_confidence, _ = compute_report_signal_quality(one_live)
    assert low_confidence is True


def test_not_low_confidence_with_two_live_sources():
    two_live = {
        "reddit": {"source": "reddit", "status": "ok", "payload": {"post_count": 50}, "fetched_at": "2026-01-01T00:00:00Z"},
        "hacker_news": {"source": "hacker_news", "status": "ok", "payload": {"hit_count": 20}, "fetched_at": "2026-01-01T00:00:00Z"},
    }
    _, low_confidence, _ = compute_report_signal_quality(two_live)
    assert low_confidence is False


def test_empty_status_does_not_count_as_live_for_low_confidence():
    """'empty' is honest (source WAS reached) but carries no corroborating
    evidence — must not be treated the same as a real 'ok' result."""
    signals = {
        "reddit": {"source": "reddit", "status": "empty", "payload": {"post_count": 0}, "fetched_at": "2026-01-01T00:00:00Z"},
        "hacker_news": {"source": "hacker_news", "status": "empty", "payload": {"hit_count": 0}, "fetched_at": "2026-01-01T00:00:00Z"},
    }
    _, low_confidence, _ = compute_report_signal_quality(signals)
    assert low_confidence is True


def test_legacy_flat_dict_signals_still_work():
    """Existing callers (predating B2) pass flat per-source dicts with no
    status/payload envelope — compute_report_signal_quality must still
    produce a sane result rather than erroring or fabricating."""
    legacy_signals = {"reddit": {"post_count": 142, "pain_frequency": "high"}}
    quality, low_confidence, per_source = compute_report_signal_quality(legacy_signals)
    assert per_source["reddit"] > 0
    assert low_confidence is True  # only 1 source present
